# backend/test_live.py
"""Standalone debug tool to verify face detection + embedding matching.
Run from project root:
    python -m backend.test_live --cam 0 --debug
Keys:
  q / ESC : quit
  r       : reload embeddings from DB
  h       : toggle Haar-only mode (sets FORCE_HAAR env at runtime)
  c       : toggle center fallback box

Environment helpers (can also be set before running):
  FACE_DEBUG=1            verbose detector logs
  FORCE_HAAR=1            skip retinaface heuristic decode
  ALLOW_CENTER_FALLBACK=0 disable injected center box when no faces
"""
from __future__ import annotations
import os, time, argparse
import cv2
import numpy as np

from .recognition_utils import compute_embedding, match_face, load_embedding_cache, model_status
from .face_utils import detect_faces  # respects env toggles
from .config import CAMERA_SOURCES
from .db import person_collection  # ensure DB connection side-effects

# Lazy flag variables (read each loop so toggling env takes effect for detect_faces)

COLORS = {
    'whitelist': (0, 200, 0),
    'blacklist': (0, 0, 255),
    'unknown': (160, 160, 160),
    'noemb': (0, 140, 255)
}

def put_text(img, text, org, color=(255,255,255), scale=0.5, thick=1):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cam', type=int, default=0, help='Camera ID key defined in config CAMERA_SOURCES')
    ap.add_argument('--raw', action='store_true', help='No recognition, only detection boxes')
    ap.add_argument('--debug', action='store_true', help='Overlay debug info (FPS, sizes)')
    ap.add_argument('--width', type=int, default=0)
    ap.add_argument('--height', type=int, default=0)
    args = ap.parse_args()

    load_embedding_cache()
    stat = model_status()
    print(f"[INFO] Model: {stat['model_loaded']} cache size={stat['cache_size']}")

    source = CAMERA_SOURCES.get(args.cam, args.cam)
    cap = cv2.VideoCapture(source)
    if args.width: cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    if args.height: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        print(f"[ERR] Cannot open camera source: {source}")
        return

    last_reload = time.time()
    t_prev = time.time()
    fps_avg = []

    while True:
        ret, frame = cap.read()
        if not ret:
            print('[WARN] Frame grab failed, exiting')
            break

        frame_disp = frame.copy()

        boxes = detect_faces(frame) if not args.raw else []

        for (x1,y1,x2,y2) in boxes:
            x1 = max(0,x1); y1 = max(0,y1); x2 = min(frame.shape[1]-1,x2); y2 = min(frame.shape[0]-1,y2)
            if x2 <= x1 or y2 <= y1: continue
            face = frame[y1:y2, x1:x2]
            label = 'Unknown'; col = COLORS['unknown']; score_txt = ''
            if not args.raw:
                emb = compute_embedding(face)
                if emb is None:
                    label = 'NoEmb'
                    col = COLORS['noemb']
                else:
                    doc, score = match_face(emb)
                    if doc:
                        flg = doc.get('flag','?')
                        name = doc.get('name','?')
                        label = f"{name}"; score_txt = f" {score:.2f}"; col = COLORS.get(flg, (255,255,0))
                        if flg == 'blacklist':
                            # thicker border for blacklist
                            cv2.rectangle(frame_disp, (x1-2,y1-2),(x2+2,y2+2),(0,0,0),2)
                    else:
                        label = 'Unknown'
                        col = COLORS['unknown']
            cv2.rectangle(frame_disp, (x1,y1),(x2,y2), col, 2)
            put_text(frame_disp, label+score_txt, (x1, max(15,y1-8)), col, 0.55, 2)

        if args.debug:
            t_now = time.time()
            dt = t_now - t_prev
            t_prev = t_now
            fps = 1.0/max(1e-6, dt)
            fps_avg.append(fps)
            if len(fps_avg) > 30: fps_avg.pop(0)
            fps_smooth = sum(fps_avg)/len(fps_avg)
            put_text(frame_disp, f"FPS {fps_smooth:.1f} (N={len(boxes)})", (10, frame_disp.shape[0]-10), (0,255,0), 0.55, 2)
            put_text(frame_disp, f"Cache:{model_status()['cache_size']}", (10, frame_disp.shape[0]-30), (0,255,255), 0.5, 1)
            if os.getenv('FORCE_HAAR','0')=='1':
                put_text(frame_disp, 'HAAR ONLY', (frame_disp.shape[1]-130,20),(0,255,255),0.55,2)

        cv2.imshow('FaceDebug', frame_disp)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord('q')):
            break
        elif key == ord('r'):
            load_embedding_cache()
            print('[INFO] Embeddings reloaded')
        elif key == ord('h'):
            cur = os.getenv('FORCE_HAAR','0')
            new = '0' if cur=='1' else '1'
            os.environ['FORCE_HAAR'] = new
            print(f"[INFO] FORCE_HAAR={new}")
        elif key == ord('c'):
            cur = os.getenv('ALLOW_CENTER_FALLBACK','1')
            new = '0' if cur=='1' else '1'
            os.environ['ALLOW_CENTER_FALLBACK'] = new
            print(f"[INFO] ALLOW_CENTER_FALLBACK={new}")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
