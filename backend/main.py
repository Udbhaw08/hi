# backend/main.py
# Fallback path handling to allow running either with `uvicorn backend.main:app` (from project root)
# or `uvicorn main:app` (from inside backend/ directory).
import subprocess
import threading
import sys
import os

try:
    # Try relative imports first (when run as a module)
    from .db import person_collection  # type: ignore
    from .admin import verify_admin  # type: ignore
    from .face_utils import detect_faces  # type: ignore
    from .recognition_utils import compute_embedding, match_face, add_person_embedding_to_cache, load_embedding_cache, model_status, switch_model, last_error  # type: ignore
    from .config import CAMERA_SOURCES, DETECTION_SKIP  # type: ignore
    from .util import camera_manager  # type: ignore
    from .realtime_pipeline import pipeline_manager, get_events_snapshot, get_report_snapshot  # Phase 3 import extended
    from .db import alerts_collection  # NEW for alerts API
except ImportError as e:
    # Fall back to absolute imports (when run directly)
    from db import person_collection
    from admin import verify_admin
    from face_utils import detect_faces
    from recognition_utils import compute_embedding, match_face, add_person_embedding_to_cache, load_embedding_cache, model_status, switch_model, last_error
    from config import CAMERA_SOURCES, DETECTION_SKIP
    from util import camera_manager
    from realtime_pipeline import pipeline_manager, get_events_snapshot, get_report_snapshot
    from db import alerts_collection

# Chatbot modules removed

# Optional insightface engine (do NOT wrap core imports above)
try:
    try:
        from .face_engine import detect_and_embed  # type: ignore
    except ImportError:
        from face_engine import detect_and_embed
except Exception:
    detect_and_embed = None

from fastapi import FastAPI, UploadFile, Form, Depends, HTTPException, File, BackgroundTasks, Body
from fastapi.responses import StreamingResponse, FileResponse, PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import WebSocket, WebSocketDisconnect
import asyncio  # Phase 3: needed for ws_pipeline sleeps
import shutil, os
import cv2
import numpy as np
from typing import List, Dict, Optional
import logging
import time
from collections import deque
import base64, json  # Added for WS frame/event messages
try:
    import psutil  # optional
except ImportError:  # fallback if psutil not installed yet
    psutil = None

try:
    from bson import ObjectId  # type: ignore
except Exception:
    ObjectId = None

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
logger = logging.getLogger("nsg")

# Optional python-multipart (module name 'multipart')
try:
    import multipart  # type: ignore  # noqa
except ImportError:
    logger.warning("python-multipart not installed in current venv; form endpoints will fail. Install with: pip install python-multipart")

app = FastAPI()

# Global variable to track server process
server_process = None

# Endpoint to start the backend server
@app.post("/admin/start_server")
async def start_server(background_tasks: BackgroundTasks, username: str = Form(...), password: str = Form(...)):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    def run_server():
        global server_process
        try:
            # Start the realtime pipeline with subprocess.Popen to avoid blocking
            server_process = subprocess.Popen(["python", "-m", "backend.realtime_pipeline"], 
                                             stdout=subprocess.PIPE, 
                                             stderr=subprocess.PIPE,
                                             text=True)
            logging.info("Started realtime pipeline process")
        except Exception as e:
            logging.error(f"Error starting realtime pipeline: {str(e)}")
    
    # Start the pipeline immediately
    run_server()
    return JSONResponse({"status": "success", "message": "Server started successfully"})

# Load embeddings at startup so existing DB persons are recognized immediately
@app.on_event("startup")
def _load_cache_startup():
    try:
        load_embedding_cache()
    except Exception as e:
        logger.error(f"Failed to preload embeddings: {e}")
    
    # Auto-start the pipeline on server startup
    try:
        global server_process
        server_process = subprocess.Popen(["python", "-m", "backend.realtime_pipeline"], 
                                         stdout=subprocess.PIPE, 
                                         stderr=subprocess.PIPE,
                                         text=True)
        logger.info("Auto-started realtime pipeline process")
    except Exception as e:
        logger.error(f"Error auto-starting realtime pipeline: {str(e)}")

# CORS (allow all for demo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("./data/person_images", exist_ok=True)

_start_time = time.time()

USE_INSIGHTFACE = os.getenv('USE_INSIGHTFACE', '1') == '1' and detect_and_embed is not None

# Phase 1 streaming perf tuning env vars
_STREAM_JPEG_QUALITY = int(os.getenv('STREAM_JPEG_QUALITY', '70'))  # lower quality -> lower latency
_STREAM_FRAME_SLEEP = float(os.getenv('STREAM_FRAME_SLEEP', '0.001'))  # small yield when no frame
_STREAM_TARGET_FPS = float(os.getenv('STREAM_TARGET_FPS', '20'))  # soft target; we drop frames above this
_DET_SKIP = int(os.getenv('STREAM_DETECTION_SKIP', str(int(os.getenv('DETECTION_SKIP', '2')))))  # allow override
_MAX_REUSE_DETS = int(os.getenv('STREAM_MAX_REUSE_DETS', '4'))  # how many skipped intervals we can reuse boxes

# (Phase 2) Additional env for pipeline stream
_PIPELINE_JPEG_QUALITY = int(os.getenv('PIPELINE_JPEG_QUALITY', str(_STREAM_JPEG_QUALITY)))
_PIPELINE_TARGET_FPS = float(os.getenv('PIPELINE_TARGET_FPS', '15'))

# WebSocket streaming env vars
_WS_JPEG_QUALITY = int(os.getenv('WS_JPEG_QUALITY', str(_STREAM_JPEG_QUALITY)))
_WS_FRAME_INTERVAL_MS = int(os.getenv('WS_FRAME_INTERVAL_MS','0'))  # 0 = send as fast as new frames available
_WS_EVENTS_EVERY = int(os.getenv('WS_EVENTS_EVERY','5'))  # send events JSON every N frames
_WS_REQUIRE_BASE64 = os.getenv('WS_REQUIRE_BASE64','0')=='1'  # force base64 if some clients need pure text

# ----- Admin Auth Dependency -----

def admin_auth(username: str = Form(...), password: str = Form(...)):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    return {"username": username}

# ----- Login Endpoint (simple, returns success) -----
@app.post("/admin/login")
async def admin_login(username: str = Form(...), password: str = Form(...)):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"status": "ok", "username": username}

# ----- Helper: extract face crop for embedding -----

def _extract_face_for_embedding(img_bgr):
    # Ensure image is valid
    if img_bgr is None or img_bgr.size == 0:
        logger.error("Invalid image provided for face extraction")
        return img_bgr, None
        
    h, w = img_bgr.shape[:2]
    
    # Try insightface detection first
    if USE_INSIGHTFACE and detect_and_embed is not None:
        try:
            faces = detect_and_embed(img_bgr)
            if faces:
                (x1,y1,x2,y2), emb, score = faces[0]
                # Ensure coordinates are valid
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w-1, x2), min(h-1, y2)
                if x2 > x1 and y2 > y1:
                    return img_bgr[y1:y2, x1:x2], emb  # return crop + embedding (already normalized)
        except Exception as e:
            logger.warning(f"InsightFace detection failed: {e}")
    
    # Fallback to legacy detection
    try:
        boxes = detect_faces(img_bgr)
    except Exception as e:
        logger.warning(f"detect_faces failed during enrollment: {e}")
        boxes = []
    
    if boxes:
        best = None; best_area = 0
        for (x1,y1,x2,y2) in boxes:
            x1,y1 = max(0,x1), max(0,y1); x2,y2 = min(w-1,x2), min(h-1,y2)
            if x2<=x1 or y2<=y1: continue
            area = (x2-x1)*(y2-y1)
            if area>best_area:
                best_area=area; best=(x1,y1,x2,y2)
        if best:
            x1,y1,x2,y2 = best
            return img_bgr[y1:y2, x1:x2], None
    
    # If all face detection methods fail, use the center of the image
    logger.info("No face detected, using center crop for embedding")
    side = min(h,w); cy,cx = h//2, w//2; half=side//2
    crop = img_bgr[cy-half:cy+half, cx-half:cx+half]
    if crop.size==0:
        crop = img_bgr
    return crop, None

# ----- Add Person Endpoint -----
@app.post("/admin/add_person")
async def add_person(
    username: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    person_id: str = Form(...),
    flag: str = Form(...),  # whitelist/blacklist
    metadata: str = Form(None),
    file: UploadFile = None,
    auth = Depends(admin_auth)
):
    if flag not in ("whitelist", "blacklist"):
        raise HTTPException(status_code=400, detail="flag must be whitelist or blacklist")
    if person_collection.find_one({"person_id": person_id}):
        raise HTTPException(status_code=400, detail="person_id already exists")
    if not file:
        raise HTTPException(status_code=400, detail="Image file required for demo")

    file_path = f"./data/person_images/{person_id}.jpg"
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        logger.error(f"Failed saving image: {e}")
        raise HTTPException(status_code=500, detail="Failed to save image")

    img = cv2.imread(file_path)
    if img is None:
        logger.error("OpenCV failed to read saved image")
        raise HTTPException(status_code=500, detail="Failed to read saved image")

    try:
        face_crop, precomputed_emb = _extract_face_for_embedding(img)
        if USE_INSIGHTFACE and precomputed_emb is not None:
            emb_vec = precomputed_emb
        else:
            emb_vec = compute_embedding(face_crop)
        if emb_vec is None:
            logger.error("Embedding computation returned None")
            raise HTTPException(status_code=500, detail={"error": "Failed to compute embedding", "model_last_error": last_error()})
    except Exception as e:
        logger.exception(f"Face detection or embedding computation failed: {e}")
        raise HTTPException(status_code=500, detail={"error": f"Face detection or embedding failed: {str(e)}", "model_last_error": last_error()})

    doc = {
        "person_id": person_id,
        "name": name,
        "flag": flag,
        "metadata": metadata,
        "image_path": file_path,
        "embedding": emb_vec.tolist()
    }
    try:
        person_collection.insert_one(doc)
        add_person_embedding_to_cache(doc)
        logger.info(f"Enrolled person_id={person_id} name={name} flag={flag}")
    except Exception as e:
        logger.exception(f"Mongo insert failed: {e}")
        raise HTTPException(status_code=500, detail="Database insert failed")
    return {"status": "success", "person_id": person_id}

# ----- List Persons Endpoint -----
@app.get("/admin/persons")
async def list_persons(username: str, password: str):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    docs = []
    for d in person_collection.find({}, {"_id": 0, "embedding": 0}):
        docs.append(d)
    return {"persons": docs}

# ----- Update Flag Endpoint -----
@app.post("/admin/update_flag")
async def update_flag(username: str = Form(...), password: str = Form(...), person_id: str = Form(...), flag: str = Form(...)):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if flag not in ("whitelist", "blacklist"):
        raise HTTPException(status_code=400, detail="Invalid flag")
    res = person_collection.update_one({"person_id": person_id}, {"$set": {"flag": flag}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Person not found")
    # reload single doc into cache (simpler: rebuild entire cache)
    load_embedding_cache()
    return {"status": "updated"}

# ----- Delete Person Endpoint -----
@app.post("/admin/delete_person")
async def delete_person(username: str = Form(...), password: str = Form(...), person_id: str = Form(...)):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    doc = person_collection.find_one({"person_id": person_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    person_collection.delete_one({"person_id": person_id})
    img_path = doc.get("image_path")
    if img_path and os.path.exists(img_path):
        try: os.remove(img_path)
        except: pass
    load_embedding_cache()
    return {"status": "deleted"}

# ----- Upload Video for Processing Endpoint -----
@app.post("/video/upload")
async def upload_video(username: str = Form(...), password: str = Form(...), file: UploadFile = File(...)):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    os.makedirs("./data/uploads", exist_ok=True)
    save_path = f"./data/uploads/{file.filename}"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    cap = cv2.VideoCapture(save_path)
    if not cap.isOpened():
        return {"status": "saved", "processed": False}
    frame_count = 0
    recognized: Dict[str, int] = {}
    unknown = 0
    while frame_count < 120:  # limit frames for demo
        ret, frame = cap.read()
        if not ret:
            break
        boxes = detect_faces(frame)
        for (x1, y1, x2, y2) in boxes:
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame.shape[1]-1, x2), min(frame.shape[0]-1, y2)
            if x2 <= x1 or y2 <= y1: continue
            face_crop = frame[y1:y2, x1:x2]
            emb = compute_embedding(face_crop)
            doc, score = match_face(emb)
            if doc:
                pid = doc.get("person_id")
                recognized[pid] = recognized.get(pid, 0) + 1
            else:
                unknown += 1
        frame_count += 1
    cap.release()
    return {"status": "processed", "recognized": recognized, "unknown": unknown}

# ----- Video streaming (multi-cam) -----

@app.get("/metrics")
async def metrics():
    uptime = time.time() - _start_time
    count_persons = person_collection.count_documents({})
    mem_mb = None
    if psutil:
        process = psutil.Process()
        mem_mb = process.memory_info().rss / (1024*1024)
    return {"uptime_sec": round(uptime,2), "persons": count_persons, "memory_mb": round(mem_mb,2) if mem_mb is not None else None}

_DEF_NO_CAM_MSG = "Cannot open camera"

# Support runtime toggle per-request (query param) for processing overlays

def gen(cam_id=0, process: bool = True, debug: bool = False):
    """Low-latency MJPEG generator.
    Phase 1 changes:
      - Uses camera_manager.get_latest_frame() (non-blocking) to avoid accumulating backlog.
      - Frame skipping based on _DET_SKIP (default from DETECTION_SKIP / env).
      - Reuses last detection results for up to _MAX_REUSE_DETS skipped intervals.
      - Adjustable JPEG quality via STREAM_JPEG_QUALITY.
      - Drops frames if processing slower than target FPS.
    """
    source = CAMERA_SOURCES.get(cam_id, 0)
    cap = camera_manager.open(source)
    if not cap or not cap.isOpened():
        camera_manager.release(source)
        raise RuntimeError(f"{_DEF_NO_CAM_MSG} {cam_id}")

    frame_index = 0
    t_prev = time.time()
    fps_q = deque(maxlen=15)

    last_dets = []  # list of dict: {bbox:(x1,y1,x2,y2), label:str, color:tuple}
    reuse_count = 0

    jpeg_params = [int(cv2.IMWRITE_JPEG_QUALITY), _STREAM_JPEG_QUALITY]
    min_frame_interval = 1.0 / max(1.0, _STREAM_TARGET_FPS)

    try:
        while True:
            # Non-blocking fetch of latest frame
            frame = camera_manager.get_latest_frame(source)
            if frame is None:
                time.sleep(_STREAM_FRAME_SLEEP)
                continue

            orig = frame
            # Shallow copy only when we draw overlays to reduce allocations
            draw_frame = orig.copy() if (process or debug) else orig

            do_detect = process and (frame_index % _DET_SKIP == 0 or reuse_count >= _MAX_REUSE_DETS or not last_dets)
            if process:
                if do_detect:
                    # fresh detection & embedding matching
                    reuse_count = 0
                    last_dets = []
                    if USE_INSIGHTFACE and detect_and_embed is not None:
                        faces = detect_and_embed(draw_frame)
                        for (x1,y1,x2,y2), emb, det_score in faces:
                            h, w = draw_frame.shape[:2]
                            x1,y1 = max(0,x1), max(0,y1); x2,y2 = min(w-1,x2), min(h-1,y2)
                            if x2 <= x1 or y2 <= y1:
                                continue
                            doc, score = match_face(emb)
                            if doc:
                                color = (0,255,0) if doc.get('flag')=='whitelist' else (0,0,255)
                                label = f"{doc.get('name','?')} ({doc.get('flag')})"
                            else:
                                color = (128,128,128)
                                label = 'Unknown'
                            last_dets.append({'bbox':(x1,y1,x2,y2),'label':label,'color':color})
                    else:
                        # legacy path
                        try:
                            boxes = detect_faces(draw_frame)
                        except Exception as e:
                            logger.error(f"detect_faces error: {e}")
                            boxes = []
                        h, w = draw_frame.shape[:2]
                        for (x1,y1,x2,y2) in boxes:
                            x1,y1 = max(0,x1), max(0,y1); x2,y2 = min(w-1,x2), min(h-1,y2)
                            if x2 <= x1 or y2 <= y1:
                                continue
                            face_crop = draw_frame[y1:y2, x1:x2]
                            emb = compute_embedding(face_crop)
                            if emb is None:
                                continue
                            doc, score = match_face(emb)
                            if doc:
                                color = (0,255,0) if doc.get('flag')=='whitelist' else (0,0,255)
                                label = f"{doc.get('name','?')} ({doc.get('flag')})"
                            else:
                                color = (128,128,128)
                                label = 'Unknown'
                            last_dets.append({'bbox':(x1,y1,x2,y2),'label':label,'color':color})
                else:
                    reuse_count += 1
                # Draw either fresh or reused dets
                for d in last_dets:
                    x1,y1,x2,y2 = d['bbox']
                    cv2.rectangle(draw_frame,(x1,y1),(x2,y2),d['color'],2)
                    cv2.putText(draw_frame,d['label'],(x1,max(15,y1-10)),cv2.FONT_HERSHEY_SIMPLEX,0.55,d['color'],2)

            if debug:
                t_now = time.time()
                fps = 1.0 / max(1e-6, (t_now - t_prev))
                t_prev = t_now
                fps_q.append(fps)
                fps_smooth = sum(fps_q)/len(fps_q)
                cv2.putText(draw_frame, f"FPS:{fps_smooth:.1f}", (10, draw_frame.shape[0]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,255,0), 2)

            # Encode
            ok, buffer = cv2.imencode('.jpg', draw_frame, jpeg_params)
            if not ok:
                frame_index += 1
                continue
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            frame_index += 1

            # Frame pacing: if we are much faster than target, short sleep; if slower, drop immediately
            elapsed = time.time() - t_prev
            if elapsed < min_frame_interval:
                time.sleep(min_frame_interval - elapsed)
    finally:
        camera_manager.release(source)

@app.get("/video/stream/{cam_id}")
def video_stream(cam_id: int, process: bool = True, debug: bool = False):
    return StreamingResponse(gen(cam_id, process=process, debug=debug), media_type='multipart/x-mixed-replace; boundary=frame')

# -------- Phase 2: Unified multi-model pipeline streaming (person/weapon/pose/actions) --------

def _pipeline_frame_generator(cam_id: int):
    """Continuously yields latest annotated frame from PipelineProcessor with low latency."""
    jpeg_params = [int(cv2.IMWRITE_JPEG_QUALITY), _PIPELINE_JPEG_QUALITY]
    min_interval = 1.0 / max(1.0, _PIPELINE_TARGET_FPS)
    # Ensure processor exists
    proc = pipeline_manager.get(cam_id)
    last_sent_ts = 0.0
    while True:
        frame, events, ts = proc.get_latest()
        if frame is None:
            time.sleep(0.01)
            continue
        # Avoid re-encoding same frame if no update
        if ts <= last_sent_ts:
            time.sleep(0.002)
            continue
        last_sent_ts = ts
        ok, buf = cv2.imencode('.jpg', frame, jpeg_params)
        if not ok:
            continue
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
        # soft pacing (if frames flood)
        time.sleep(min_interval * 0.2)

@app.get('/pipeline/stream/{cam_id}')
async def pipeline_stream(cam_id: int):
    """MJPEG stream of the consolidated real-time pipeline (weapons, pose, actions)."""
    # Accessing generator auto-starts processor
    return StreamingResponse(_pipeline_frame_generator(cam_id), media_type='multipart/x-mixed-replace; boundary=frame')

@app.get('/pipeline/events/{cam_id}')
async def pipeline_events(cam_id: int):
    """Return latest structured events (JSON) for a camera pipeline (for frontend / LLM consumption)."""
    snapshot = get_events_snapshot(cam_id)
    return snapshot

@app.get('/pipeline/status')
async def pipeline_status():
    """List active pipeline processors and basic stats."""
    # naive internal access (no lock method exposed) by fetching a couple cam snapshots from known sources
    out = []
    for idx in range(len(CAMERA_SOURCES)):
        proc = pipeline_manager.get(idx)
        _frame, events, ts = proc.get_latest()
        out.append({'cam_id': idx, 'last_ts': ts, 'events': len(events)})
    return {'pipelines': out}

@app.get('/pipeline/report/{cam_id}')
async def pipeline_report(cam_id: int):
    """Structured aggregated report (actions, identities, recent timeline) for a camera."""
    if 'get_report_snapshot' in globals():
        return get_report_snapshot(cam_id)
    # backward compatibility if function missing
    snap = get_events_snapshot(cam_id)
    return {'cam_id': cam_id, 'timestamp': snap.get('timestamp'), 'actions': {}, 'identities': {}, 'timeline': [], 'events': snap.get('events', [])}

@app.get("/admin/person_image/{person_id}")
async def get_person_image(person_id: str, username: str, password: str):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    doc = person_collection.find_one({"person_id": person_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    path = doc.get("image_path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image missing")
    return FileResponse(path)

# Health
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/admin/reload_embeddings")
async def reload_embeddings(username: str = Form(...), password: str = Form(...)):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    load_embedding_cache()
    return {"status": "reloaded"}

@app.post("/admin/rebuild_embeddings")
async def rebuild_embeddings(username: str = Form(...), password: str = Form(...)):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    updated = 0
    failed = 0
    for doc in person_collection.find({}):
        path = doc.get("image_path")
        if not path or not os.path.exists(path):
            failed += 1
            continue
        img = cv2.imread(path)
        if img is None:
            failed += 1
            continue
        crop, pre_emb = _extract_face_for_embedding(img)
        if USE_INSIGHTFACE and pre_emb is not None:
            emb = pre_emb
        else:
            emb = compute_embedding(crop)
        if emb is None:
            failed += 1
            continue
        person_collection.update_one({"_id": doc["_id"]}, {"$set": {"embedding": emb.tolist()}})
        updated += 1
    load_embedding_cache()
    return {"status": "done", "updated": updated, "failed": failed}

@app.get("/admin/model_status")
async def get_model_status(username: str, password: str):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return model_status()

@app.post("/admin/switch_model")
async def post_switch_model(username: str = Form(...), password: str = Form(...), target: str = Form(...)):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    ok = False
    msg = ""
    try:
        ok = switch_model(target)
        msg = "switched" if ok else "switch_failed"
    except Exception as e:
        msg = f"error: {e}"  # minimal error leak
    return {"success": ok, "message": msg, "status": model_status()}

@app.post("/admin/self_test")
async def admin_self_test(username: str = Form(...), password: str = Form(...), file: UploadFile = File(...)):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    data = file.file.read()
    import numpy as np, cv2
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image")
    crop, pre_emb = _extract_face_for_embedding(img)
    if USE_INSIGHTFACE and pre_emb is not None:
        emb = pre_emb
    else:
        emb = compute_embedding(crop)
    if emb is None:
        raise HTTPException(status_code=500, detail={"error": "Embedding failed", "model_last_error": last_error(), "model_status": model_status()})
    return {"embedding_dim": int(len(emb)), "model_status": model_status(), "insightface": USE_INSIGHTFACE}

@app.get("/admin/camera_status")
async def camera_status(username: str, password: str):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"cameras": camera_manager.status()}

@app.get("/admin/detect_test")
async def detect_test(cam_id: int, username: str, password: str):
    if not verify_admin(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    source = CAMERA_SOURCES.get(cam_id, 0)
    cap = camera_manager.open(source)
    if not cap or not cap.isOpened():
        camera_manager.release(source)
        raise HTTPException(status_code=400, detail="Camera open failed")
    ret, frame = cap.read()
    camera_manager.release(source)
    if not ret or frame is None:
        raise HTTPException(status_code=400, detail="Frame read failed")
    boxes = detect_faces(frame)
    return {"boxes": boxes, "count": len(boxes), "shape": frame.shape[:2]}

@app.websocket('/ws/pipeline/{cam_id}')
async def ws_pipeline(websocket: WebSocket, cam_id: int):
    """WebSocket low-latency pipeline stream.
    Binary mode (default): each message is a binary JPEG frame. A small JSON text message with events is sent every _WS_EVENTS_EVERY frames.
    Base64 mode (if WS_REQUIRE_BASE64=1 or client passes ?mode=base64): each message is JSON: {type:'frame', ts:float, jpeg_b64:str} plus periodic {type:'events', events:[...]}. 
    Query parameters:
      - 'mode': 'binary' or 'base64' (frame transport)
      - 'proc': 'full', 'object', or 'face' (processing pipeline)
    """
    await websocket.accept()
    try:
        mode = websocket.query_params.get('mode','binary')
        if _WS_REQUIRE_BASE64:
            mode = 'base64'
        proc = pipeline_manager.get(cam_id)
        # Optional per-connection processing mode override
        proc_mode = websocket.query_params.get('proc')
        if proc_mode in ('full','object','face'):
            try:
                proc.set_mode(proc_mode)
            except Exception:
                pass
        last_ts = 0.0
        frame_counter = 0
        jpeg_params = [int(cv2.IMWRITE_JPEG_QUALITY), _WS_JPEG_QUALITY]
        min_interval = _WS_FRAME_INTERVAL_MS / 1000.0 if _WS_FRAME_INTERVAL_MS>0 else 0.0
        # Include current processing mode in init for UI awareness
        try:
            cur_mode = getattr(proc, 'mode', 'full')
        except Exception:
            cur_mode = 'full'
        await websocket.send_text(json.dumps({'type':'init','cam_id':cam_id,'mode':mode,'proc':cur_mode}))
        while True:
            frame, events, ts = proc.get_latest()
            if frame is None or ts <= last_ts:
                await asyncio.sleep(0.005)
                continue
            last_ts = ts
            ok, buf = cv2.imencode('.jpg', frame, jpeg_params)
            if not ok:
                continue
            frame_counter += 1
            if mode == 'binary':
                # send frame first
                try:
                    await websocket.send_bytes(buf.tobytes())
                except Exception:
                    break
                if frame_counter % _WS_EVENTS_EVERY == 0:
                    try:
                        await websocket.send_text(json.dumps({'type':'events','ts':ts,'events':events}))
                    except Exception:
                        break
            else:  # base64 JSON
                b64 = base64.b64encode(buf.tobytes()).decode('ascii')
                try:
                    await websocket.send_text(json.dumps({'type':'frame','ts':ts,'jpeg_b64':b64}))
                except Exception:
                    break
                if frame_counter % _WS_EVENTS_EVERY == 0:
                    try:
                        await websocket.send_text(json.dumps({'type':'events','ts':ts,'events':events}))
                    except Exception:
                        break
            if min_interval>0:
                await asyncio.sleep(min_interval)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    # closed

@app.get('/alerts')
async def list_alerts(cam_id: Optional[int] = None, limit: int = 50, since_ts: Optional[float] = None):
    """Return recent persisted alert documents (refined logic)."""
    q = {}
    if cam_id is not None:
        q['cam_id'] = cam_id
    if since_ts is not None:
        q['ts'] = {'$gte': since_ts}
    cur = alerts_collection.find(q).sort('ts', -1).limit(max(1,min(limit,500)))
    out = []
    for d in cur:
        d['_id'] = str(d['_id'])
        out.append(d)
    return {'alerts': out}

@app.get('/alerts/report/{alert_id}')
async def alert_report(alert_id: str, format: str = 'txt'):
    """Generate a mock incident report for a specific alert.
    Customize the template below (search for TEMPLATE_START) to change layout/fields.
    """
    if ObjectId is None:
        return PlainTextResponse('bson not installed', status_code=500)
    try:
        oid = ObjectId(alert_id)
    except Exception:
        return PlainTextResponse('invalid id', status_code=400)
    doc = alerts_collection.find_one({'_id': oid})
    if not doc:
        return PlainTextResponse('not found', status_code=404)
    # --- TEMPLATE_START (edit safely) ---
    ts_iso = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(doc.get('ts',0)))
    lines = [
        '=== AI SECURITY INCIDENT REPORT ===',
        f'Generated: {time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())}',
        '',
        'SUMMARY:',
        f"At {ts_iso}, on Camera {doc.get('cam_id')} (Track {doc.get('track_id')}),",
        f"Person: {doc.get('name') or 'Unknown'} (ID: {doc.get('person_id') or 'N/A'})",
        f"Flagged as: {doc.get('flag') or 'unknown'}",
        f"Action: {doc.get('action')}",
        f"Weapons detected: {','.join(doc.get('weapon_classes') or []) or 'none'}",
        f"Alert Type: {doc.get('type')}",
        f"Match Score: {doc.get('match_score')}", 
        '',
        'Reason:',
        doc.get('description','(no description)'),
        '',
        'POSE KEYPOINTS (first 10 shown):',
        str((doc.get('pose_keypoints') or [])[:10]),
        '',
        'RAW JSON:',
        # Provide raw dict minus internal fields
        # (You can replace with sanitized subset)
        '',
    ]
    # --- TEMPLATE_END ---
    report_text = '\n'.join(lines) + '\n'
    if format == 'json':
        d = dict(doc)
        d['_id'] = alert_id
        return d
    filename = f"incident_{alert_id}.txt"
    return PlainTextResponse(report_text, headers={'Content-Disposition': f'attachment; filename={filename}'})

@app.post('/pipeline/render/{cam_id}')
async def set_pipeline_render(cam_id: int, on: bool = Form(...)):
    """Enable/disable overlay rendering for a pipeline processor (useful to reduce CPU when no clients need overlays)."""
    try:
        proc = pipeline_manager.get(cam_id)
        proc._render = bool(on)
        return {'cam_id': cam_id, 'render': proc._render}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/pipeline/render/{cam_id}')
async def get_pipeline_render(cam_id: int):
    try:
        proc = pipeline_manager.get(cam_id)
        return {'cam_id': cam_id, 'render': bool(getattr(proc, '_render', False))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# Chatbot API endpoints removed

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
