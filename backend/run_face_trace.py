# backend/run_face_trace.py
"""Standalone Face Trace runner with visible camera window.

Usage:
   python -m backend.run_face_trace --ref <path_to_reference_image> [--cam 1]

Press 'q' to quit.
"""
import sys, os, time, argparse, threading
import cv2
import numpy as np

# Sound alert (Windows)
try:
    import winsound
    def _beep():
        """Play a detection alert sound."""
        threading.Thread(target=lambda: winsound.Beep(1200, 500), daemon=True).start()
except ImportError:
    def _beep():
        print('\a')  # terminal bell fallback

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from backend.face_trace import FaceTracer
from backend.config import CAMERA_SOURCES


# ─────────────────────────────────────────────────
#  Threaded camera reader (eliminates lag)
# ─────────────────────────────────────────────────
class CameraReader:
    """Reads camera in a background thread — always holds the latest frame."""

    def __init__(self, source, backend=cv2.CAP_DSHOW):
        self.cap = cv2.VideoCapture(source, backend)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = cv2.VideoCapture(source)
        self.frame = None
        self.ret = False
        self._lock = threading.Lock()
        self._running = False

        if self.cap.isOpened():
            # Lower buffer to reduce latency
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._running = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()

    def _read_loop(self):
        while self._running:
            ret, frame = self.cap.read()
            with self._lock:
                self.ret = ret
                self.frame = frame

    def read(self):
        with self._lock:
            return self.ret, self.frame.copy() if self.frame is not None else None

    def is_opened(self):
        return self.cap.isOpened()

    def release(self):
        self._running = False
        time.sleep(0.1)
        self.cap.release()


def main():
    parser = argparse.ArgumentParser(description="Face Trace — Find a person from camera")
    parser.add_argument('--ref', required=True, help="Path to reference image of the target person")
    parser.add_argument('--cam', type=int, default=1, help="Camera index (default: 1 = laptop webcam)")
    parser.add_argument('--threshold', type=float, default=0.35, help="Match threshold (default: 0.35)")
    parser.add_argument('--output', default='./data/face_trace_results', help="Output directory for saved matches")
    args = parser.parse_args()

    # ── 1. Load reference ──
    tracer = FaceTracer()
    print(f"\n{'='*60}")
    print(f"  FACE TRACE — Multi-Modal Person Search")
    print(f"{'='*60}")
    print(f"  Reference : {args.ref}")
    print(f"  Camera    : {args.cam}")
    print(f"  Threshold : {args.threshold}")
    print(f"  Output    : {args.output}")
    print(f"{'='*60}\n")

    ok, msg = tracer.set_reference(args.ref)
    if not ok:
        print(f"[ERROR] {msg}")
        sys.exit(1)

    print(f"[OK] {msg}")
    features = tracer.get_status()['features']
    print(f"     Face={features['face']}  Body={features['body']}  Clothing={features['clothing']}\n")

    # Override thresholds
    import backend.face_trace as ft_module
    ft_module.MATCH_THRESHOLD = args.threshold
    ft_module.CONFIDENT_THRESHOLD = args.threshold + 0.10

    # ── 2. Open camera (threaded — no lag) ──
    print(f"[INFO] Opening camera {args.cam}...")

    cam = CameraReader(args.cam)
    if not cam.is_opened():
        print(f"[ERROR] Cannot open camera {args.cam}")
        sys.exit(1)

    # Give camera a moment to warm up
    time.sleep(0.5)

    print(f"[OK] Camera opened (threaded reader). Press 'q' to quit.\n")

    os.makedirs(args.output, exist_ok=True)
    frame_count = 0
    found = False
    start_time = time.time()
    last_detections = []   # cache for smooth display

    WINDOW = "Face Trace - Person Search"
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, 960, 720)

    try:
        while True:
            ret, frame = cam.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            frame_count += 1
            display = frame.copy()
            elapsed = time.time() - start_time

            # ── Run detection every 5th frame (reduce CPU load) ──
            if frame_count % 5 == 0:
                last_detections = tracer.process_frame(frame)

            # ── Draw cached detections on every frame (smooth display) ──
            for det in last_detections:
                score = det['combined_score']
                scores = det.get('scores', {})

                # Only draw when it's a real match — skip non-matches
                if score < args.threshold:
                    continue

                # Face box (green)
                if det.get('face_box'):
                    fx1, fy1, fx2, fy2 = map(int, det['face_box'])
                    cv2.rectangle(display, (fx1, fy1), (fx2, fy2), (0, 255, 0), 3)

                # Body box (cyan)
                if det.get('body_box'):
                    bx1, by1, bx2, by2 = map(int, det['body_box'])
                    cv2.rectangle(display, (bx1, by1), (bx2, by2), (255, 200, 0), 2)

                # Score labels
                anchor = det.get('face_box') or det.get('body_box')
                if anchor:
                    ax, ay = int(anchor[0]), int(anchor[1])
                    label = f"Score: {score:.2f}"
                    lc = (0, 255, 0) if score >= args.threshold else (100, 100, 100)
                    cv2.putText(display, label, (ax, max(18, ay - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, lc, 2)
                    y_off = max(18, ay - 32)
                    for k, v in scores.items():
                        cv2.putText(display, f"{k}:{v:.2f}", (ax, y_off),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
                        y_off -= 16

                # ── FIRST MATCH → save, beep, stop ──
                if score >= args.threshold and not found:
                    found = True
                    _beep()   # 🔊 Sound alert!

                    ts = time.strftime("%Y%m%d_%H%M%S")
                    fname = f"match_{ts}_s{score:.2f}.jpg"
                    save_path = os.path.join(args.output, fname)
                    cv2.imwrite(save_path, display)

                    clean_path = os.path.join(args.output, f"clean_{fname}")
                    cv2.imwrite(clean_path, frame)

                    print(f"\n  🔔 PERSON DETECTED!  score={score:.3f}")
                    print(f"     face={scores.get('face',0):.2f}  body={scores.get('body',0):.2f}  clothing={scores.get('clothing',0):.2f}")
                    print(f"     Saved → {save_path}")

            # ── HUD overlay ──
            h, w = display.shape[:2]
            overlay = display.copy()
            cv2.rectangle(overlay, (0, 0), (w, 50), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, display, 0.4, 0, display)

            if found:
                cv2.putText(display, "Face Trace | PERSON FOUND!", (10, 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            else:
                cv2.putText(display, "Face Trace | SEARCHING...", (10, 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)

            cv2.putText(display, f"Time: {elapsed:.0f}s", (w - 150, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

            feat = tracer.get_status()['features']
            feat_text = f"Face:{'ON' if feat['face'] else 'OFF'}  Body:{'ON' if feat['body'] else 'OFF'}  Cloth:{'ON' if feat['clothing'] else 'OFF'}"
            cv2.putText(display, feat_text, (10, h - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)

            # ── Show frame ──
            cv2.imshow(WINDOW, display)

            # ── Auto-stop after detection (show for 3 sec) ──
            if found:
                print(f"\n{'='*60}")
                print(f"  ✅ PERSON FOUND!")
                print(f"  Result saved in: {args.output}")
                print(f"{'='*60}")
                cv2.waitKey(3000)
                break

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\n[INFO] Quit by user")
                break

    finally:
        cam.release()
        cv2.destroyAllWindows()

    print(f"\nDone in {elapsed:.1f}s")
    if found:
        print(f"Result saved in: {os.path.abspath(args.output)}")


if __name__ == '__main__':
    main()
