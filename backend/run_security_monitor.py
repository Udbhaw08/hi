# backend/run_security_monitor.py
import sys
import os
import time
import threading
import cv2
import numpy as np
import base64
import requests
from datetime import datetime

# Optimization: InsightFace environment
os.environ['INSIGHTFACE_DET_SIZE'] = '640x640'

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from backend.face_engine import detect_and_embed
    from backend.recognition_utils import match_face, load_embedding_cache
    from backend.config import CAMERA_SOURCES
    HAS_INSIGHTFACE = True
except ImportError:
    HAS_INSIGHTFACE = False

def _beep(freq=1200, dur=400):
    try:
        import winsound
        threading.Thread(target=lambda: winsound.Beep(freq, dur), daemon=True).start()
    except: pass

class SecurityMonitor:
    def __init__(self, cam_id=1):
        self.cam_id = cam_id
        self.running = False
        self.lock = threading.Lock()
        self.latest_frame = None
        self.display_frame = None
        self.last_results = []
        self.last_alert_time = {}
        
        print("[INFO] Loading InsightFace & Database...")
        load_embedding_cache()

    def ai_worker(self):
        """Heavy lifting InsightFace thread."""
        print("[INFO] InsightFace Worker started.")
        while self.running:
            process_frame = None
            with self.lock:
                if self.latest_frame is not None:
                    process_frame = self.latest_frame.copy()
                    self.latest_frame = None 
            
            if process_frame is None:
                time.sleep(0.01)
                continue

            try:
                results = detect_and_embed(process_frame)
                
                temp_results = []
                for (box, emb, d_score) in results:
                    doc, m_score = match_face(emb)
                    if doc and doc.get('flag') in ('whitelist', 'blacklist'):
                        temp_results.append({'box': box, 'doc': doc, 'score': m_score})
                        
                        # Alerting
                        pid = doc.get('person_id')
                        if time.time() - self.last_alert_time.get(pid, 0) > 20: # 20s throttle
                            self.last_alert_time[pid] = time.time()
                            threading.Thread(target=self._send_unified_alert, args=(process_frame, doc, m_score, box), daemon=True).start()
                            if doc.get('flag') == 'blacklist': _beep()
                
                with self.lock:
                    self.last_results = temp_results
                    
            except Exception as e:
                print(f"[ERROR] AI: {e}")
            
            time.sleep(0.01)

    def _send_unified_alert(self, frame, doc, score, box):
        """Send alert to the MAIN backend (Port 8000) for the dynamic dashboard."""
        try:
            # Crop the person's face/body for the dashboard
            x1,y1,x2,y2 = map(int, box)
            h,w = frame.shape[:2]
            # Add some padding for the photo
            pad = 50
            crop = frame[max(0,y1-pad):min(h,y2+pad), max(0,x1-pad):min(w,x2+pad)]
            if crop.size == 0: crop = frame
            
            _, buffer = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
            img_b64 = base64.b64encode(buffer).decode('utf-8')
            
            payload = {
                "ts": time.time(),
                "cam_id": self.cam_id,
                "type": "FACE_RECOGNITION",
                "action": "Identity Matched",
                "person_id": doc.get('person_id'),
                "name": doc.get('name'),
                "flag": doc.get('flag'),
                "match_score": float(score),
                "image": f"data:image/jpeg;base64,{img_b64}",
                "description": f"Security Monitor matched {doc.get('name')} on Cam {self.cam_id}"
            }
            # Send to main backend (8000)
            requests.post("http://localhost:8000/api/alerts", json=payload, timeout=2)
            # Also send to detection system (5000) for safety
            requests.post("http://localhost:5000/api/detection", json=payload, timeout=2)
            print(f"[ALERT] Sent alert for {doc.get('name')}")
        except Exception as e:
            print(f"[ERROR] Alert failed: {e}")

    def run(self):
        source = CAMERA_SOURCES.get(self.cam_id, self.cam_id)
        cap = cv2.VideoCapture(source)
        if not cap.isOpened(): cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not cap.isOpened(): return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.running = True
        threading.Thread(target=self.ai_worker, daemon=True).start()

        print(f"[OK] InsightFace Security Monitor active on Cam {self.cam_id}.")

        while self.running:
            ret, frame = cap.read()
            if not ret: continue

            with self.lock:
                self.latest_frame = frame
            
            display = frame.copy()
            with self.lock:
                for res in self.last_results:
                    x1,y1,x2,y2 = res['box']
                    doc = res['doc']
                    color = (0, 255, 0) if doc.get('flag') == 'whitelist' else (0, 0, 255)
                    cv2.rectangle(display, (x1,y1), (x2,y2), color, 2)
                    cv2.rectangle(display, (x1,y1-25), (x2,y1), color, -1)
                    cv2.putText(display, f"{doc.get('name')}", (x1+5, y1-8), 0, 0.6, (255,255,255), 2)

            cv2.imshow("InsightFace Monitor", display)
            if cv2.waitKey(1) & 0xFF == ord('q'): break

        self.running = False
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--cam", type=int, default=1)
    SecurityMonitor(cam_id=p.parse_args().cam).run()
