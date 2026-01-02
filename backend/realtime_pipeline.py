# backend/realtime_pipeline.py
"""Real-time multi-model pipeline consolidated for backend streaming.
Origin: refactored from test_realtime_pipeline.py (removed cv2 window logic).
Provides:
  - PipelineProcessor: stateful per camera pipeline (detection, tracking, pose, action classification)
  - pipeline_manager: registry to obtain processors per cam id
  - get_events_snapshot(cam_id): returns recent stable events for polling / JSON output

Phase 1 goals: low-latency, reuse latest frame from camera_manager; stabilize action labels.
"""
import os, time, threading
import numpy as np
import cv2
import onnxruntime as ort
from collections import deque, defaultdict
from .bytetracker_utils import SimpleTracker  # type: ignore
from .action_engine import classify as classify_action_track  # type: ignore
from .utils_pose_rules import DEFAULT_PARAMS, aiming_metrics  # type: ignore
from .config import CAMERA_SOURCES  # type: ignore
from .util import camera_manager  # type: ignore
from .recognition_utils import compute_embedding, match_face, find_best_local_match, compare_to_local_image, load_embedding_cache, LOCAL_IMG_THRESHOLD  # type: ignore
from .config import MATCH_THRESHOLD  # type: ignore
from .db import alerts_collection  # type: ignore
from .face_utils import detect_faces  # fallback lightweight face detector

# Optional insightface engine (SCRFD + glintr100) for identity embeddings
try:
    from .face_engine import detect_and_embed as _if_detect_and_embed  # type: ignore
except Exception:
    _if_detect_and_embed = None
USE_INSIGHTFACE_PIPELINE = os.getenv('USE_INSIGHTFACE', '1') == '1' and _if_detect_and_embed is not None

CAM0_DEBUG = os.getenv('CAM0_DEBUG','0') == '1'

CLASSES = ["person","gun","knife"]
PERSON_ID = 0
WEAPON_IDS = {1,2}
INPUT_SZ = 640
CONF_THRES = float(os.getenv('DET_CONF','0.40'))
IOU_THRES = float(os.getenv('DET_IOU','0.45'))
# Tunables
WEAPON_CENTER_DIST_NORM = float(os.getenv('WEAPON_CENTER_DIST_NORM','1.3'))
WEAPON_SCORE_PROMOTE = float(os.getenv('WEAPON_SCORE_PROMOTE','0.40'))
ACTION_PERSIST_FRAMES = int(os.getenv('ACTION_PERSIST_FRAMES','8'))
ACTION_SMOOTH_WIN = int(os.getenv('ACTION_SMOOTH_WIN','5'))  # majority vote window
PIPE_TARGET_FPS = float(os.getenv('PIPE_TARGET_FPS','15'))
# Phase 3 env vars
FACE_REID_INTERVAL = int(os.getenv('FACE_REID_INTERVAL','10'))  # frames between re-id attempts per cam
FACE_MIN_SIZE = int(os.getenv('FACE_MIN_SIZE','40'))
FACE_ID_PERSIST_FRAMES = int(os.getenv('FACE_ID_PERSIST_FRAMES','30'))
FACE_TOP_FRACTION = float(os.getenv('FACE_TOP_FRACTION','0.45'))  # portion of bbox height assumed to contain face
TIMELINE_MAX_EVENTS = int(os.getenv('TIMELINE_MAX_EVENTS','500'))
SUSPICIOUS_ACTIONS = set(os.getenv('SUSPICIOUS_ACTIONS','Weapon,Aiming,Fighting,Running,Loitering').split(','))
ALERT_THROTTLE_SEC = float(os.getenv('ALERT_THROTTLE_SEC','3.0'))

# ONNX providers preference
_PROVIDERS = ['CPUExecutionProvider']
try:
    av = ort.get_available_providers()
    for cand in ('CUDAExecutionProvider','DmlExecutionProvider'):
        if cand in av:
            _PROVIDERS = [cand,'CPUExecutionProvider']
            break
except Exception:
    pass

# Lazy model containers (shared)
_yolo_session = None
_pose_session = None
_models_lock = threading.Lock()

def _load_models():
    global _yolo_session, _pose_session
    with _models_lock:
        if _yolo_session is None:
            so = ort.SessionOptions()
            try:
                so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            except Exception:
                pass
            intra = int(os.getenv('ORT_INTRA_THREADS','0'))
            if intra > 0:
                try:
                    so.intra_op_num_threads = intra
                except Exception:
                    pass
            _yolo_session = ort.InferenceSession(os.path.join('backend','models','best.onnx'), providers=_PROVIDERS, sess_options=so)
        if _pose_session is None:
            so2 = ort.SessionOptions()
            try:
                so2.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            except Exception:
                pass
            _pose_session = ort.InferenceSession(os.path.join('backend','models','pose_landmark_full.onnx'), providers=_PROVIDERS, sess_options=so2)
    return _yolo_session, _pose_session

# Utilities

def _xywh2xyxy(x):
    y = np.copy(x)
    y[:,0] = x[:,0] - x[:,2]/2
    y[:,1] = x[:,1] - x[:,3]/2
    y[:,2] = x[:,0] + x[:,2]/2
    y[:,3] = x[:,1] + x[:,3]/2
    return y

def _bbox_iou(box, boxes):
    x1 = np.maximum(box[0], boxes[:,0]); y1 = np.maximum(box[1], boxes[:,1])
    x2 = np.minimum(box[2], boxes[:,2]); y2 = np.minimum(box[3], boxes[:,3])
    inter = np.maximum(0,x2-x1)*np.maximum(0,y2-y1)
    area1 = (box[2]-box[0])*(box[3]-box[1]); area2 = (boxes[:,2]-boxes[:,0])*(boxes[:,3]-boxes[:,1])
    return inter / (area1 + area2 - inter + 1e-6)

def _nms(boxes, scores, iou_thres):
    if len(boxes)==0: return []
    idxs = scores.argsort()[::-1]
    keep = []
    while len(idxs):
        i = idxs[0]; keep.append(i)
        if len(idxs)==1: break
        ious = _bbox_iou(boxes[i], boxes[idxs[1:]])
        idxs = idxs[1:][ious < iou_thres]
    return keep

class PipelineProcessor:
    def __init__(self, cam_id: int):
        self.cam_id = cam_id
        # processing mode: 'full' (default), 'object' (object/pose/actions only), 'face' (identity-only via InsightFace)
        self.mode = os.getenv('PIPELINE_MODE', 'full')
        self.tracker = SimpleTracker()
        self.prev_poses = {}
        self.track_action_history = {}
        self.track_recent_labels = defaultdict(lambda: deque(maxlen=ACTION_SMOOTH_WIN))
        self.last_events = []  # list of event dicts from last processed frame
        self.last_frame = None
        self.last_proc_ts = 0.0
        self.frame_lock = threading.Lock()
        self.stop_flag = False
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.frame_counter = 0
        self.track_face_identity = {}  # tid -> {'person_id':..., 'name':..., 'flag':..., 'score':float, 'last_frame':int}
        self.track_face_votes = {}     # tid -> deque of recent person_id predictions
        self.timeline = deque(maxlen=TIMELINE_MAX_EVENTS)  # list of significant events (identity/action changes)
        self._last_face_results = None  # cache faces per processed frame when using insightface
        self._alert_last_ts = {}  # key -> last ts
        self.track_pose_hist = defaultdict(lambda: deque(maxlen=DEFAULT_PARAMS.get('pose_history_len',5)))
        # Load DB embeddings and local person images once per processor start
        try:
            load_embedding_cache()
        except Exception:
            pass

    def set_mode(self, mode: str):
        """Set processing mode for this camera pipeline.
        Allowed: 'full', 'object', 'face'."""
        if mode not in ('full','object','face'):
            return
        self.mode = mode

    def _yolo_infer(self, frame, yolo_session):
        h0,w0 = frame.shape[:2]
        img_rs = cv2.resize(frame,(INPUT_SZ,INPUT_SZ))
        blob = img_rs[:,:,::-1].transpose(2,0,1)[None].astype(np.float32)/255.0
        out = yolo_session.run(None,{yolo_session.get_inputs()[0].name: blob})[0]
        if out.ndim==3:
            if out.shape[1]==7:
                pred = out[0].transpose(1,0)
            else:
                pred = out[0]
        else:
            pred = out
        if pred.shape[1] != 7:
            return np.empty((0,6),dtype=np.float32)
        boxes_xywh = pred[:, :4]
        cls_scores = pred[:, 4:]
        cls_ids = np.argmax(cls_scores, axis=1)
        confs = cls_scores[np.arange(cls_scores.shape[0]), cls_ids]
        mask = confs >= CONF_THRES
        if not np.any(mask):
            return np.empty((0,6),dtype=np.float32)
        boxes_xywh = boxes_xywh[mask]; confs = confs[mask]; cls_ids = cls_ids[mask]
        boxes_xyxy = _xywh2xyxy(boxes_xywh)
        scale_w = w0 / INPUT_SZ; scale_h = h0 / INPUT_SZ
        boxes_xyxy[:,[0,2]] *= scale_w; boxes_xyxy[:,[1,3]] *= scale_h
        boxes_xyxy[:,0] = np.clip(boxes_xyxy[:,0],0,w0-1); boxes_xyxy[:,2] = np.clip(boxes_xyxy[:,2],0,w0-1)
        boxes_xyxy[:,1] = np.clip(boxes_xyxy[:,1],0,h0-1); boxes_xyxy[:,3] = np.clip(boxes_xyxy[:,3],0,h0-1)
        keep = _nms(boxes_xyxy, confs, IOU_THRES)
        if not keep: return np.empty((0,6),dtype=np.float32)
        boxes_xyxy = boxes_xyxy[keep]; confs = confs[keep]; cls_ids = cls_ids[keep]
        return np.concatenate([boxes_xyxy, confs[:,None], cls_ids[:,None]], axis=1).astype(np.float32)

    def _pose_infer(self, crop, pose_session):
        if crop.size==0: return None
        try:
            img = cv2.resize(crop,(256,256))
            blob = img.transpose(2,0,1)[None].astype(np.float32)/255.0
            out = pose_session.run(None,{pose_session.get_inputs()[0].name: blob})[0]
            return out[0]
        except Exception:
            return None

    def _extra_weapon_score(self, person_box, weapon_dets):
        if weapon_dets.shape[0] == 0:
            return 0.0
        x1,y1,x2,y2,_ = person_box
        pcx = (x1+x2)/2.0; pcy = (y1+y2)/2.0
        pw = max(1.0, x2-x1); ph = max(1.0, y2-y1)
        best = 0.0
        for wd in weapon_dets:
            wx1,wy1,wx2,wy2,conf,cid = wd
            wcx = (wx1+wx2)/2.0; wcy = (wy1+wy2)/2.0
            nd = (((wcx-pcx)/pw)**2 + ((wcy-pcy)/ph)**2) ** 0.5
            if nd <= WEAPON_CENTER_DIST_NORM:
                proximity_boost = max(0.0, 1.0 - nd / WEAPON_CENTER_DIST_NORM)
                score = conf * (0.5 + 0.5*proximity_boost)
                if score > best:
                    best = score
        return best

    def _smooth_action(self, tid, action):
        q = self.track_recent_labels[tid]
        q.append(action)
        if len(q) < 2:
            return action
        # majority vote
        counts = {}
        for a in q:
            counts[a] = counts.get(a,0)+1
        best = max(counts.items(), key=lambda kv: kv[1])[0]
        return best

    def _maybe_emit_alert(self, ts: float, track_event: dict, weapon_classes: list):
        """Refined alert emission rules:
        - Whitelist: never generate alert (even if weapon/gun); action label forced to Normal.
        - Blacklist: alert only if gun present AND suspicious action AND pose keypoints available.
        - Unknown (no person_id): alert only if gun present AND suspicious action.
        Stores pose_keypoints & weapon_classes in alert doc.
        """
        try:
            ident = track_event.get('identity') or {}
            action = track_event.get('action')
            flag = ident.get('flag')
            person_id = ident.get('person_id')
            pose = track_event.get('pose')  # list or None
            gun_present = 'gun' in weapon_classes
            suspicious = action in SUSPICIOUS_ACTIONS
            # Whitelist suppression
            if flag == 'whitelist':
                return  # no alert
            alert_type = None
            if flag == 'blacklist':
                if gun_present and suspicious and pose:  # all required
                    alert_type = 'BLACKLIST_THREAT'
            elif person_id is None:  # unknown
                if gun_present and suspicious:
                    alert_type = 'UNKNOWN_THREAT'
            if not alert_type:
                return
            key = (self.cam_id, track_event['track_id'], alert_type)
            last = self._alert_last_ts.get(key, 0.0)
            if ts - last < ALERT_THROTTLE_SEC:
                return
            self._alert_last_ts[key] = ts
            doc = {
                'ts': ts,
                'cam_id': self.cam_id,
                'track_id': track_event['track_id'],
                'type': alert_type,
                'action': action,
                'bbox': track_event.get('bbox'),
                'weapon_classes': weapon_classes,
                'person_id': person_id,
                'name': ident.get('name'),
                'flag': flag,
                'match_score': ident.get('score'),
                'pose_keypoints': pose,
                'description': f"{alert_type} action={action} guns={gun_present}",
                'inserted_at': time.time()
            }
            alerts_collection.insert_one(doc)
            track_event['alert'] = True
            track_event['alert_type'] = alert_type
        except Exception:
            pass

    def _loop(self):
        yolo_session, pose_session = _load_models()
        min_interval = 1.0 / max(1.0, PIPE_TARGET_FPS)
        while not self.stop_flag:
            start = time.time()
            source = CAMERA_SOURCES.get(self.cam_id, 0)
            frame = camera_manager.get_latest_frame(source)
            if frame is None:
                time.sleep(0.002)
                continue
            self.frame_counter += 1
            self._last_face_results = None  # invalidate per frame
            events = []
            # Identity-only pipeline when requested (applies to any camera)
            if self.mode == 'face':
                try:
                    faces = []
                    # Preferred: use insightface SCRFD+glintr if available
                    if USE_INSIGHTFACE_PIPELINE and _if_detect_and_embed is not None:
                        faces = _if_detect_and_embed(frame) or []  # list of ((x1,y1,x2,y2), emb, score)
                        # convert to unified form below
                        unified = []
                        for item in faces:
                            try:
                                (fx1,fy1,fx2,fy2), femb, fscore = item
                                unified.append(((int(fx1),int(fy1),int(fx2),int(fy2)), femb, float(fscore)))
                            except Exception:
                                continue
                    else:
                        # Fallback: use lightweight face detector (retinaface/haar) to get boxes, then compute embedding via ArcFace
                        boxes = detect_faces(frame) or []
                        unified = []
                        for (x1,y1,x2,y2) in boxes:
                            try:
                                # crop face area, pad a bit
                                h,w = frame.shape[:2]
                                pad = 4
                                fx1 = max(0, x1-pad); fy1 = max(0, y1-pad); fx2 = min(w-1, x2+pad); fy2 = min(h-1, y2+pad)
                                crop = frame[fy1:fy2, fx1:fx2]
                                if crop.size == 0:
                                    continue
                                emb = compute_embedding(crop)
                                unified.append(((fx1,fy1,fx2,fy2), emb, 0.0))
                            except Exception:
                                continue
                    if CAM0_DEBUG:
                        print(f"[CAM0] unified faces: {len(unified)}")
                    # Process unified face list
                    for (fx1,fy1,fx2,fy2), femb, fscore in (unified or []):
                        # ignore tiny faces
                        if (fx2-fx1) < 24 or (fy2-fy1) < 24:
                            continue
                        try:
                            if CAM0_DEBUG:
                                print(f"[CAM0] face box: {(fx1,fy1,fx2,fy2)} emb_present={femb is not None}")
                            # Compare against DB embeddings first
                            doc, db_score = match_face(femb) if femb is not None else (None, None)
                            if CAM0_DEBUG:
                                print(f"[CAM0] db_match: {bool(doc)} score={db_score}")
                            local_pid, local_score = find_best_local_match(femb) if femb is not None else (None, None)
                            if CAM0_DEBUG:
                                print(f"[CAM0] local_match: {local_pid} score={local_score}")
                            identity = None
                            # Decide final identity conservatively: prefer DB match but require local-image confirmation when available
                            if doc and db_score is not None and db_score >= MATCH_THRESHOLD:
                                pid = doc.get('person_id')
                                confirmed = True
                                if local_pid is not None and local_pid == pid:
                                    if local_score is None or local_score < LOCAL_IMG_THRESHOLD:
                                        confirmed = False
                                if confirmed:
                                    identity = {'person_id': pid, 'name': doc.get('name'), 'flag': doc.get('flag'), 'score': float(db_score)}
                            # If DB not matched, but local image gives a strong match, use local match and try to load doc
                            if identity is None and local_pid is not None and local_score is not None and local_score >= LOCAL_IMG_THRESHOLD:
                                try:
                                    from .db import person_collection
                                    doc_local = person_collection.find_one({'person_id': local_pid})
                                except Exception:
                                    doc_local = None
                                identity = {'person_id': local_pid, 'name': doc_local.get('name') if doc_local else None, 'flag': doc_local.get('flag') if doc_local else None, 'score': float(local_score)}
                            # Unknown if still none
                            if identity is None:
                                identity = {'person_id': None, 'name': None, 'flag': None, 'score': float(db_score) if db_score is not None else (float(local_score) if local_score is not None else 0.0)}
                            # Build event for this face
                            ev = {
                                'type': 'person',
                                'track_id': -1,
                                'action': 'IdentityOnly',
                                'bbox': [float(fx1), float(fy1), float(fx2), float(fy2)],
                                'identity': identity,
                                'duration_s': 0.0,
                                'pose': None,
                                'weapon_score': 0.0,
                                'weapon_classes': []
                            }
                            events.append(ev)
                            if CAM0_DEBUG:
                                print(f"[CAM0] appended identity event: {identity}")
                        except Exception:
                            # log minimal info and continue
                            print('[WARN] Cam0 face processing error')
                            continue
                except Exception as e:
                    print(f'[ERROR] cam0 identity pipeline failed: {e}')
                    if CAM0_DEBUG:
                        import traceback; traceback.print_exc()
                # If no faces detected, ensure at least a fallback unknown box is emitted
                if not events:
                    try:
                        fb_boxes = detect_faces(frame) or []
                        for (x1,y1,x2,y2) in fb_boxes:
                            events.append({
                                'type': 'person', 'track_id': -1, 'action': 'IdentityOnly',
                                'bbox': [float(x1), float(y1), float(x2), float(y2)],
                                'identity': {'person_id': None, 'name': None, 'flag': None, 'score': 0.0},
                                'duration_s': 0.0, 'pose': None, 'weapon_score': 0.0, 'weapon_classes': []
                            })
                        # As last resort, inject center box
                        if not events:
                            h,w = frame.shape[:2]
                            cw,ch = int(w*0.28), int(h*0.28)
                            cx1 = w//2 - cw//2; cy1 = h//2 - ch//2
                            cx2 = cx1 + cw; cy2 = cy1 + ch
                            events.append({
                                'type': 'person', 'track_id': -1, 'action': 'IdentityOnly',
                                'bbox': [float(cx1), float(cy1), float(cx2), float(cy2)],
                                'identity': {'person_id': None, 'name': None, 'flag': None, 'score': 0.0},
                                'duration_s': 0.0, 'pose': None, 'weapon_score': 0.0, 'weapon_classes': []
                            })
                    except Exception:
                        # safety: inject center box on failure
                        h,w = frame.shape[:2]
                        cw,ch = int(w*0.28), int(h*0.28)
                        cx1 = w//2 - cw//2; cy1 = h//2 - ch//2
                        cx2 = cx1 + cw; cy2 = cy1 + ch
                        events.append({
                            'type': 'person', 'track_id': -1, 'action': 'IdentityOnly',
                            'bbox': [float(cx1), float(cy1), float(cx2), float(cy2)],
                            'identity': {'person_id': None, 'name': None, 'flag': None, 'score': 0.0},
                            'duration_s': 0.0, 'pose': None, 'weapon_score': 0.0, 'weapon_classes': []
                        })

                annotated = frame.copy()
                for ev in events:
                    x1,y1,x2,y2 = map(int, ev['bbox'])
                    ident = ev.get('identity')
                    flag = ident.get('flag') if ident else None
                    base_label = f"{ident.get('name') or ident.get('person_id') or 'Unknown'}"
                    if flag:
                        base_label += f' [{flag}]'
                    color = (0,255,0)
                    if flag == 'blacklist': color = (0,0,255)
                    cv2.rectangle(annotated,(x1,y1),(x2,y2),color,2)
                    cv2.putText(annotated, base_label, (x1, max(14,y1-8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                with self.frame_lock:
                    self.last_frame = annotated
                    self.last_events = events
                    self.last_proc_ts = start
                elapsed = time.time() - start
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                # Render identity-only overlays and continue pacing
                annotated = frame.copy()
                for ev in events:
                    x1,y1,x2,y2 = map(int, ev['bbox'])
                    ident = ev.get('identity')
                    flag = ident.get('flag') if ident else None
                    base_label = f"{ident.get('name') or ident.get('person_id') or 'Unknown'}"
                    if flag:
                        base_label += f' [{flag}]'
                    color = (0,255,0)
                    if flag == 'blacklist': color = (0,0,255)
                    cv2.rectangle(annotated,(x1,y1),(x2,y2),color,2)
                    cv2.putText(annotated, base_label, (x1, max(14,y1-8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                with self.frame_lock:
                    self.last_frame = annotated
                    self.last_events = events
                    self.last_proc_ts = start
                elapsed = time.time() - start
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                continue
            # --- Object/pose/actions pipeline ---
            dets = self._yolo_infer(frame, yolo_session)
            if dets.shape[0]:
                person_dets = dets[dets[:,5]==PERSON_ID]
                weapon_dets = dets[np.isin(dets[:,5], list(WEAPON_IDS))]
            else:
                person_dets = dets
                weapon_dets = dets
            weapon_classes_frame = [CLASSES[int(wd[5])] for wd in weapon_dets]
            tracks = self.tracker.update(person_dets, now_ts=start)
            
            # Weapons overlay
            for wdet in weapon_dets:
                x1,y1,x2,y2,conf,cid = wdet
                events.append({
                    'type':'weapon', 'cls': CLASSES[int(cid)], 'confidence': float(conf),
                    'bbox': [float(x1),float(y1),float(x2),float(y2)]
                })
            # Track loop
            for tid, tr in tracks.items():
                x1,y1,x2,y2,_ = tr['bbox']
                crop = frame[int(y1):int(y2), int(x1):int(x2)]
                pose_arr = self._pose_infer(crop, pose_session)
                # update per-track pose history for smoothing
                ph = self.track_pose_hist.get(tid)
                if ph is None:
                    ph = deque(maxlen=DEFAULT_PARAMS.get('pose_history_len',5))
                    self.track_pose_hist[tid] = ph
                ph.append(pose_arr)
                # expose pose_history on track dict for utils
                tr['pose_history'] = list(ph)
                pose_list = pose_arr.tolist() if pose_arr is not None else None
                prev_pose = self.prev_poses.get(tid)
                action, weapon_score = classify_action_track(tr, pose_arr, prev_pose, weapon_dets.tolist())
                extra_score = self._extra_weapon_score(tr['bbox'], weapon_dets)
                if extra_score > weapon_score:
                    weapon_score = extra_score
                if action == 'Normal' and weapon_score >= WEAPON_SCORE_PROMOTE:
                    if pose_arr is not None and aiming_metrics(pose_arr).get('right_angle',0) >= DEFAULT_PARAMS['aim_angle_min']:
                        action = 'Aiming'
                    else:
                        action = 'Weapon'
                hist = self.track_action_history.get(tid, deque(maxlen=ACTION_PERSIST_FRAMES))
                if action == 'Normal' and any(a in ('Weapon','Aiming') for a in hist):
                    action = 'Weapon'
                hist.append(action)
                self.track_action_history[tid] = hist
                action = self._smooth_action(tid, action)
                self.prev_poses[tid] = pose_arr
                person_event = {
                    'type':'person','track_id': int(tid), 'action': action,
                    'bbox':[float(x1),float(y1),float(x2),float(y2)],
                    'weapon_score': float(weapon_score),
                    'duration_s': float(self.tracker.duration(tr)),
                    'speed': float(self.tracker.avg_speed(tr)),
                    'pose': pose_list,
                    'weapon_classes': weapon_classes_frame
                }
                events.append(person_event)
                # AFTER events.append for person, perform face re-id occasionally (skip in object-only mode)
                # Face crop heuristic (top fraction of person bbox)
                x1,y1,x2,y2,_ = tr['bbox']
                bw = x2 - x1; bh = y2 - y1
                face_changed = False
                if self.mode != 'object' and bw >= FACE_MIN_SIZE and bh >= FACE_MIN_SIZE and (self.frame_counter % FACE_REID_INTERVAL == 0):
                    if USE_INSIGHTFACE_PIPELINE:
                        if self._last_face_results is None:
                            try:
                                self._last_face_results = _if_detect_and_embed(frame)  # list of ((x1,y1,x2,y2), emb, score)
                            except Exception:
                                self._last_face_results = []
                        best_face = None; best_iou = 0.0
                        tx1,ty1,tx2,ty2,_ = tr['bbox']
                        for (fx1,fy1,fx2,fy2), femb, fscore in (self._last_face_results or []):
                            # quick reject if face box not in upper portion of track
                            if fy1 > (ty1 + bh * FACE_TOP_FRACTION):
                                continue
                            # IoU
                            ix1 = max(tx1, fx1); iy1 = max(ty1, fy1)
                            ix2 = min(tx2, fx2); iy2 = min(ty2, fy2)
                            iw = max(0, ix2 - ix1); ih = max(0, iy2 - iy1)
                            inter = iw * ih
                            if inter <= 0: continue
                            t_area = (tx2-tx1)*(ty2-ty1)
                            f_area = (fx2-fx1)*(fy2-fy1)
                            iou = inter / (t_area + f_area - inter + 1e-6)
                            if iou > best_iou:
                                best_iou = iou; best_face = ((fx1,fy1,fx2,fy2), femb)
                        emb = None
                        if best_face is not None:
                            emb = best_face[1]
                    else:
                        # fallback crop top fraction and run ArcFace
                        fy2 = y1 + bh * FACE_TOP_FRACTION
                        fx1 = max(0,int(x1)); fy1 = max(0,int(y1)); fx2 = max(0,int(x2)); fy2 = max(0,int(fy2))
                        face_crop = frame[int(fy1):int(fy2), int(fx1):int(fx2)]
                        emb = compute_embedding(face_crop) if face_crop.size>0 else None
                    if emb is not None:
                        doc, score = match_face(emb)
                        pid_pred = None; identity_dict = None
                        if doc and score is not None and score >= MATCH_THRESHOLD:
                            pid_pred = doc.get('person_id')
                            identity_dict = {
                                'person_id': pid_pred,
                                'name': doc.get('name'),
                                'flag': doc.get('flag'),
                                'score': float(score)
                            }
                        if pid_pred is not None:
                            dq = self.track_face_votes.get(tid)
                            if dq is None:
                                dq = deque(maxlen=7)
                                self.track_face_votes[tid] = dq
                            dq.append(pid_pred)
                            counts = {}
                            for v in dq: counts[v] = counts.get(v,0)+1
                            best_pid, best_cnt = max(counts.items(), key=lambda kv: kv[1])
                            if best_cnt >= (len(dq)//2 + 1):
                                cur = self.track_face_identity.get(tid)
                                if (not cur) or cur.get('person_id') != best_pid:
                                    self.timeline.append({'ts': start, 'cam_id': self.cam_id, 'track_id': int(tid), 'event':'identity_change', 'person_id': best_pid})
                                self.track_face_identity[tid] = {**identity_dict, 'last_frame': self.frame_counter}
                        else:
                            cur = self.track_face_identity.get(tid)
                            if cur and (self.frame_counter - cur.get('last_frame',0) > FACE_ID_PERSIST_FRAMES):
                                self.timeline.append({'ts': start, 'cam_id': self.cam_id, 'track_id': int(tid), 'event':'identity_lost'})
                                self.track_face_identity.pop(tid, None)
                # Track action transitions for timeline
                # Retrieve last recorded action for this track (store in tracker dict)
                last_action_key = '_last_action'
                current_action = events[-1]['action'] if events and events[-1].get('track_id')==int(tid) else None
                if current_action:
                    prev_act = tr.get(last_action_key)
                    if prev_act != current_action:
                        self.timeline.append({'ts': start, 'cam_id': self.cam_id, 'track_id': int(tid), 'event':'action_change', 'from': prev_act, 'to': current_action})
                        tr[last_action_key] = current_action
            # Inject identity info into person events (skip in object-only mode)
            for ev in events:
                if ev['type']=='person':
                    if self.mode != 'object':
                        ident = self.track_face_identity.get(ev['track_id'])
                        if ident:
                            ev['identity'] = {k: ident[k] for k in ('person_id','name','flag','score') if k in ident}
                            # Whitelist force Normal label
                            if ident.get('flag')=='whitelist' and ev['action'] in ('Weapon','Aiming'):
                                ev['action'] = 'Normal'
                    self._maybe_emit_alert(start, ev, ev.get('weapon_classes',[]))
            # Render overlays
            annotated = frame.copy()
            for ev in events:
                if ev['type']=='weapon':
                    x1,y1,x2,y2 = map(int, ev['bbox'])
                    cv2.rectangle(annotated,(x1,y1),(x2,y2),(0,0,255),2)
                    cv2.putText(annotated,f"{ev['cls']}", (x1,max(12,y1-6)), cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,255),2)
                else:
                    x1,y1,x2,y2 = map(int, ev['bbox'])
                    action = ev['action']
                    ident = ev.get('identity')
                    flag = ident.get('flag') if ident else None
                    base_label = f"ID {ev['track_id']}:{action}"
                    if ident:
                        base_label += f" {ident.get('name') or ident.get('person_id')}" + (f"[{flag[0].upper()}]" if flag else '')
                    if ev.get('alert'):
                        base_label = "! " + base_label
                    color = (0,255,0)
                    if flag == 'blacklist':
                        color = (0,0,255)
                    elif action == 'Aiming': color = (0,165,255)
                    elif action == 'Weapon': color = (0,140,255)
                    elif action == 'Loitering': color = (255,255,0)
                    elif action == 'Running': color = (255,0,0)
                    elif action == 'Fighting': color = (128,0,255)
                    cv2.rectangle(annotated,(x1,y1),(x2,y2),color,2)
                    cv2.putText(annotated,base_label,(x1,max(14,y1-8)),cv2.FONT_HERSHEY_SIMPLEX,0.5,color,2)
            with self.frame_lock:
                self.last_frame = annotated
                self.last_events = events
                self.last_proc_ts = start
            # pacing
            elapsed = time.time() - start
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)

    def get_latest(self):
        with self.frame_lock:
            return self.last_frame, list(self.last_events), self.last_proc_ts

    def get_timeline(self):
        return list(self.timeline)

    def stop(self):
        self.stop_flag = True

# Manager for multiple cameras
class _PipelineManager:
    def __init__(self):
        self._procs = {}
        self._lock = threading.Lock()
    def get(self, cam_id:int):
        with self._lock:
            if cam_id not in self._procs:
                self._procs[cam_id] = PipelineProcessor(cam_id)
            return self._procs[cam_id]
    def snapshot_events(self, cam_id:int):
        proc = self.get(cam_id)
        _, events, ts = proc.get_latest()
        return {'cam_id': cam_id, 'timestamp': ts, 'events': events}
    def snapshot_report(self, cam_id:int):
        proc = self.get(cam_id)
        _, events, ts = proc.get_latest()
        timeline = proc.get_timeline()[-100:]  # last 100 events
        # aggregate counts
        action_counts = {}
        identity_counts = {}
        for ev in events:
            if ev['type']=='person':
                action = ev.get('action')
                if action:
                    action_counts[action] = action_counts.get(action,0)+1
                ident = ev.get('identity')
                if ident:
                    pid = ident.get('person_id')
                    if pid:
                        identity_counts[pid] = identity_counts.get(pid,0)+1
        return {
            'cam_id': cam_id,
            'timestamp': ts,
            'actions': action_counts,
            'identities': identity_counts,
            'timeline': timeline
        }
    def stop_all(self):
        with self._lock:
            for p in self._procs.values():
                p.stop()
            self._procs.clear()

pipeline_manager = _PipelineManager()

def get_events_snapshot(cam_id:int):
    return pipeline_manager.snapshot_events(cam_id)

def get_report_snapshot(cam_id:int):
    return pipeline_manager.snapshot_report(cam_id)
