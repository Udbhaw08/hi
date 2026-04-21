# backend/face_trace.py
"""Face Trace — Multi-Modal Person Search from Camera.

Combines three detection modalities for maximum accuracy:
  1. Face Recognition  (InsightFace SCRFD+GlintR100 / ArcFace fallback)
  2. Body Re-ID         (OSNet x1.0 trained on MSMT17)
  3. Clothing Analysis  (HSV colour histograms on upper/lower body)

Usage:
  face_tracer.set_reference(image_path_or_ndarray)
  face_tracer.start_search(cam_id=0)
  # ... poll face_tracer.get_status() ...
  face_tracer.get_results()
"""

import os, time, threading, logging
from datetime import datetime
from collections import deque

import cv2
import numpy as np
import onnxruntime as ort

logger = logging.getLogger("face_trace")

# ---------- Import existing backend modules ----------
try:
    from .face_engine import detect_and_embed as _insightface_detect  # type: ignore
except Exception:
    _insightface_detect = None
try:
    from .face_utils import detect_faces as _fallback_face_detect  # type: ignore
except Exception:
    from face_utils import detect_faces as _fallback_face_detect
try:
    from .recognition_utils import compute_embedding as _arcface_embedding  # type: ignore
except Exception:
    from recognition_utils import compute_embedding as _arcface_embedding
try:
    from .util import camera_manager  # type: ignore
    from .config import CAMERA_SOURCES  # type: ignore
except ImportError:
    from util import camera_manager
    from config import CAMERA_SOURCES

# ---------- Paths & tunables ----------
_BASE_DIR = os.path.dirname(__file__)
_OSNET_PATH = os.path.join(_BASE_DIR, 'models', 'osnet_x1_0_msmt17.onnx')

# Combined‑score weights (Face is now the primary gatekeeper)
FACE_WEIGHT = float(os.getenv('FT_FACE_WEIGHT', '0.80'))
BODY_WEIGHT = float(os.getenv('FT_BODY_WEIGHT', '0.15'))
CLOTHING_WEIGHT = float(os.getenv('FT_CLOTHING_WEIGHT', '0.05'))

# Minimum face score required — prevents false matches from body/clothing alone
MIN_FACE_SCORE = float(os.getenv('FT_MIN_FACE_SCORE', '0.35'))
# New: Minimum body score to avoid matching random background textures
MIN_BODY_SCORE = float(os.getenv('FT_MIN_BODY_SCORE', '0.40'))

MATCH_THRESHOLD = float(os.getenv('FT_MATCH_THRESHOLD', '0.40'))
# Higher bar when all three modalities agree
CONFIDENT_THRESHOLD = float(os.getenv('FT_CONFIDENT_THRESHOLD', '0.60'))
SAVE_TOP_N = int(os.getenv('FT_SAVE_TOP_N', '10'))
MAX_SEARCH_SECONDS = int(os.getenv('FT_MAX_SEARCH_SEC', '300'))

# ONNX provider auto‑detect
_PROVIDERS = ['CPUExecutionProvider']
try:
    _av = ort.get_available_providers()
    for _cand in ('CUDAExecutionProvider', 'DmlExecutionProvider'):
        if _cand in _av:
            _PROVIDERS = [_cand, 'CPUExecutionProvider']
            break
except Exception:
    pass

# OpenCV HOG full‑body person detector (supplementary)
_hog = cv2.HOGDescriptor()
_hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


# ═══════════════════════════════════════════════════════════════════
#  OSNet Encoder  (body re‑identification)
# ═══════════════════════════════════════════════════════════════════
class _OSNetEncoder:
    """Lazy‑loaded OSNet x1.0 MSMT17 — 512‑dim person appearance embedding."""

    def __init__(self):
        self._session: ort.InferenceSession | None = None
        self._loaded = False

    # ---- private ----
    def _load(self):
        if self._loaded:
            return
        if not os.path.exists(_OSNET_PATH):
            logger.warning("OSNet model not found at %s", _OSNET_PATH)
            return
        try:
            so = ort.SessionOptions()
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._session = ort.InferenceSession(_OSNET_PATH, providers=_PROVIDERS, sess_options=so)
            self._loaded = True
            inp = self._session.get_inputs()[0]
            logger.info("OSNet loaded — input: %s shape: %s", inp.name, inp.shape)
        except Exception as exc:
            logger.error("Failed to load OSNet: %s", exc)

    # ---- public ----
    def encode(self, person_crop_bgr: np.ndarray):
        """Return normalised 512‑dim embedding for a person crop (BGR)."""
        self._load()
        if self._session is None:
            return None
        try:
            # OSNet expects (1, 3, 256, 128) — RGB, ImageNet‑normalised
            img = cv2.resize(person_crop_bgr, (128, 256))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            img = (img - mean) / std
            blob = np.ascontiguousarray(img.transpose(2, 0, 1)[None])      # (1,3,256,128)

            inp_name = self._session.get_inputs()[0].name
            out = self._session.run(None, {inp_name: blob})[0]
            emb = np.squeeze(out).astype(np.float32)
            n = np.linalg.norm(emb)
            return (emb / n) if n > 0 else None
        except Exception as exc:
            logger.error("OSNet inference error: %s", exc)
            return None


# ═══════════════════════════════════════════════════════════════════
#  Clothing Colour Analyser
# ═══════════════════════════════════════════════════════════════════
class _ClothingAnalyser:
    """HSV colour‑histogram features for upper (torso) and lower (legs) body."""

    @staticmethod
    def extract(person_crop_bgr: np.ndarray):
        """Return a normalised feature vector (96‑dim) or None."""
        if person_crop_bgr is None or person_crop_bgr.size == 0:
            return None
        try:
            h, w = person_crop_bgr.shape[:2]
            if h < 30 or w < 15:
                return None

            # Upper body ≈ 25‑55% height, lower body ≈ 55‑85% height
            # (skips head region at top, feet at bottom)
            upper = person_crop_bgr[int(h * 0.25):int(h * 0.55), :]
            lower = person_crop_bgr[int(h * 0.55):int(h * 0.85), :]

            parts: list[np.ndarray] = []
            for region in (upper, lower):
                if region.size == 0:
                    parts.append(np.zeros(48, dtype=np.float32))
                    continue
                hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
                h_hist = cv2.calcHist([hsv], [0], None, [16], [0, 180]).flatten()
                s_hist = cv2.calcHist([hsv], [1], None, [8], [0, 256]).flatten()
                v_hist = cv2.calcHist([hsv], [2], None, [8], [0, 256]).flatten()
                mean_hsv = hsv.mean(axis=(0, 1))   # 3 values
                std_hsv = hsv.std(axis=(0, 1))      # 3 values
                parts.append(np.concatenate([h_hist, s_hist, v_hist, mean_hsv, std_hsv]))

            vec = np.concatenate(parts).astype(np.float32)
            n = np.linalg.norm(vec)
            return (vec / n) if n > 0 else None
        except Exception as exc:
            logger.error("Clothing feature extraction failed: %s", exc)
            return None

    @staticmethod
    def compare(a, b) -> float:
        """Cosine similarity between two clothing feature vectors."""
        if a is None or b is None:
            return 0.0
        ml = min(len(a), len(b))
        a, b = a[:ml], b[:ml]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a / na, b / nb))


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _iou(a, b) -> float:
    xa = max(a[0], b[0]); ya = max(a[1], b[1])
    xb = min(a[2], b[2]); yb = min(a[3], b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    if inter <= 0:
        return 0.0
    aa = (a[2] - a[0]) * (a[3] - a[1])
    ab = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (aa + ab - inter + 1e-6)


def _estimate_body_from_face(face_bbox, frame_shape):
    """Heuristic: face ≈ 1/7 of body height, ~2.5× face width."""
    fx1, fy1, fx2, fy2 = face_bbox
    fh = fy2 - fy1
    fw = fx2 - fx1
    fcx = (fx1 + fx2) / 2
    h, w = frame_shape[:2]

    body_h = fh * 6.5
    body_w = fw * 2.5
    bx1 = int(max(0, fcx - body_w / 2))
    by1 = int(max(0, fy1 - fh * 0.3))
    bx2 = int(min(w - 1, fcx + body_w / 2))
    by2 = int(min(h - 1, fy1 + body_h))
    if bx2 <= bx1 or by2 <= by1:
        return None
    return (bx1, by1, bx2, by2)


def _detect_persons_hog(frame):
    """Return list of (x1,y1,x2,y2) person boxes via OpenCV HOG."""
    h, w = frame.shape[:2]
    scale = min(1.0, 640 / max(h, w))
    small = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
    try:
        rects, _ = _hog.detectMultiScale(small, winStride=(8, 8), padding=(4, 4), scale=1.05)
    except Exception:
        return []
    boxes = []
    for (rx, ry, rw, rh) in rects:
        boxes.append((int(rx / scale), int(ry / scale),
                       int((rx + rw) / scale), int((ry + rh) / scale)))
    return boxes


# ═══════════════════════════════════════════════════════════════════
#  Face Tracer — the main engine
# ═══════════════════════════════════════════════════════════════════
class FaceTracer:
    """Multi‑modal person search engine."""

    def __init__(self):
        self.osnet = _OSNetEncoder()
        self.clothing = _ClothingAnalyser()

        # Reference features
        self.ref_face_emb: np.ndarray | None = None
        self.ref_body_emb: np.ndarray | None = None
        self.ref_clothing_feat: np.ndarray | None = None
        self.ref_image: np.ndarray | None = None

        # Search state
        self.searching = False
        self._thread: threading.Thread | None = None
        self._stop = False
        self.status = "idle"        # idle | extracting | ready | searching | found | timeout | stopped | error
        self.matches: list[dict] = []
        self.best_match: dict | None = None
        self.output_dir = os.path.join(_BASE_DIR, '..', 'data', 'face_trace_results')
        self._start_ts: float = 0.0
        self._lock = threading.Lock()

    # -----------------------------------------------------------
    # 1. Reference extraction
    # -----------------------------------------------------------
    def set_reference(self, image_or_path):
        """Extract face + body + clothing features from a reference person image.

        Returns (ok: bool, message: str).
        """
        self.status = "extracting"
        self.ref_face_emb = None
        self.ref_body_emb = None
        self.ref_clothing_feat = None
        self.matches = []
        self.best_match = None

        # Load image
        if isinstance(image_or_path, str):
            img = cv2.imread(image_or_path)
        elif isinstance(image_or_path, np.ndarray):
            img = image_or_path
        else:
            self.status = "error"
            return False, "Invalid input — pass a file path or numpy array"

        if img is None or img.size == 0:
            self.status = "error"
            return False, "Failed to read reference image"

        self.ref_image = img.copy()
        h, w = img.shape[:2]
        face_box = None

        # ── Face embedding ──
        if _insightface_detect is not None:
            try:
                faces = _insightface_detect(img)
                if faces:
                    (fx1, fy1, fx2, fy2), emb, score = faces[0]
                    self.ref_face_emb = emb
                    face_box = (fx1, fy1, fx2, fy2)
                    logger.info("Ref face embedding (InsightFace) det_score=%.3f", score)
            except Exception as exc:
                logger.warning("InsightFace ref failed: %s", exc)

        if self.ref_face_emb is None:
            # ArcFace fallback
            try:
                boxes = _fallback_face_detect(img)
                if boxes:
                    x1, y1, x2, y2 = boxes[0]
                    crop = img[max(0, y1):min(h - 1, y2), max(0, x1):min(w - 1, x2)]
                    if crop.size > 0:
                        self.ref_face_emb = _arcface_embedding(crop)
                        face_box = (x1, y1, x2, y2)
                        logger.info("Ref face embedding (ArcFace fallback)")
            except Exception as exc:
                logger.warning("ArcFace ref failed: %s", exc)

        # ── Body region ──
        person_crop = img   # default: full image
        if face_box is not None:
            bb = _estimate_body_from_face(face_box, img.shape)
            if bb is not None:
                bx1, by1, bx2, by2 = bb
                pc = img[by1:by2, bx1:bx2]
                if pc.size > 0:
                    person_crop = pc

        # ── Body embedding (OSNet) ──
        try:
            self.ref_body_emb = self.osnet.encode(person_crop)
            if self.ref_body_emb is not None:
                logger.info("Ref body embedding (OSNet) dim=%d", len(self.ref_body_emb))
        except Exception as exc:
            logger.warning("OSNet ref failed: %s", exc)

        # ── Clothing features ──
        try:
            self.ref_clothing_feat = self.clothing.extract(person_crop)
            if self.ref_clothing_feat is not None:
                logger.info("Ref clothing features dim=%d", len(self.ref_clothing_feat))
        except Exception as exc:
            logger.warning("Clothing ref failed: %s", exc)

        available = []
        if self.ref_face_emb is not None:
            available.append("face")
        if self.ref_body_emb is not None:
            available.append("body")
        if self.ref_clothing_feat is not None:
            available.append("clothing")

        if not available:
            self.status = "error"
            return False, "Could not extract any feature from the reference image"

        self.status = "ready"
        return True, f"Features extracted: {', '.join(available)}"

    # -----------------------------------------------------------
    # 2. Scoring
    # -----------------------------------------------------------
    def _score(self, face_emb=None, body_emb=None, clothing_feat=None):
        """Compute adaptive‑weight combined match score."""
        scores: dict[str, float] = {}
        weights: dict[str, float] = {}

        def _cos(a, b):
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            if na == 0 or nb == 0:
                return 0.0
            return max(0.0, float(np.dot(a / na, b / nb)))

        if face_emb is not None and self.ref_face_emb is not None:
            scores['face'] = _cos(face_emb, self.ref_face_emb)
            weights['face'] = FACE_WEIGHT
        if body_emb is not None and self.ref_body_emb is not None:
            scores['body'] = _cos(body_emb, self.ref_body_emb)
            weights['body'] = BODY_WEIGHT
        if clothing_feat is not None and self.ref_clothing_feat is not None:
            scores['clothing'] = self.clothing.compare(clothing_feat, self.ref_clothing_feat)
            weights['clothing'] = CLOTHING_WEIGHT

        if not scores:
            return 0.0, {}

        # ── GATE 1: Face rejection ──
        # If face was detected but doesn't match well enough, reject immediately
        if 'face' in scores and scores['face'] < MIN_FACE_SCORE:
            return 0.0, scores

        # ── GATE 2: Body rejection ──
        # If body was detected but is very weak, don't let it trigger a match alone
        if 'body' in scores and scores['body'] < MIN_BODY_SCORE:
             # If we don't have a face, this is likely a false positive on background
             if 'face' not in scores:
                 return 0.0, scores

        # ── Renormalisation Logic ──
        # If the reference has a face, but the detection DOES NOT, we penalise the total weight
        # so that body+clothing alone cannot easily hit the threshold.
        tw = sum(weights.values())
        
        # If reference has face but frame doesn't, we "fill" the missing weight to dilute the score
        if self.ref_face_emb is not None and 'face' not in scores:
            tw = max(tw, FACE_WEIGHT + BODY_WEIGHT + CLOTHING_WEIGHT)

        combined = sum(scores[k] * weights[k] for k in scores) / tw if tw else 0.0
        return combined, scores

    # -----------------------------------------------------------
    # 3. Per‑frame processing
    # -----------------------------------------------------------
    def process_frame(self, frame):
        """Process one frame. Returns list of detection dicts sorted by score."""
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        detections = []

        # ─ Detect faces ─
        faces_raw: list[dict] = []
        if _insightface_detect is not None:
            try:
                for (fx1, fy1, fx2, fy2), emb, sc in (_insightface_detect(frame) or []):
                    if (fx2 - fx1) < 10 or (fy2 - fy1) < 10:
                        continue
                    faces_raw.append({'box': (int(fx1), int(fy1), int(fx2), int(fy2)),
                                      'emb': emb, 'det': sc})
            except Exception:
                pass

        if not faces_raw:
            try:
                for bx in (_fallback_face_detect(frame) or []):
                    x1, y1, x2, y2 = int(bx[0]), int(bx[1]), int(bx[2]), int(bx[3])
                    if (x2 - x1) < 10 or (y2 - y1) < 10:
                        continue
                    crop = frame[max(0, y1):min(h - 1, y2), max(0, x1):min(w - 1, x2)]
                    emb = _arcface_embedding(crop) if crop.size > 0 else None
                    faces_raw.append({'box': (x1, y1, x2, y2), 'emb': emb, 'det': 0.5})
            except Exception:
                pass

        # ─ HOG person detections (full‑body) ─
        hog_boxes = _detect_persons_hog(frame)

        # ─ Build multi‑modal detections from faces ─
        for fd in faces_raw:
            fx1, fy1, fx2, fy2 = fd['box']
            face_emb = fd['emb']

            body_box = _estimate_body_from_face(fd['box'], frame.shape)

            # Prefer a matching HOG box if available
            if body_box and hog_boxes:
                best_iou, best_hog = 0, None
                for hb in hog_boxes:
                    v = _iou(body_box, hb)
                    if v > best_iou:
                        best_iou, best_hog = v, hb
                if best_hog and best_iou > 0.15:
                    body_box = best_hog

            body_emb, clothing_feat = None, None
            if body_box:
                bx1, by1, bx2, by2 = [max(0, c) for c in body_box[:2]] + [min(w - 1, body_box[2]), min(h - 1, body_box[3])]
                if bx2 > bx1 and by2 > by1:
                    pc = frame[by1:by2, bx1:bx2]
                    if pc.size > 0:
                        body_emb = self.osnet.encode(pc)
                        clothing_feat = self.clothing.extract(pc)

            combined, indiv = self._score(face_emb, body_emb, clothing_feat)
            detections.append({
                'face_box': [fx1, fy1, fx2, fy2],
                'body_box': list(body_box) if body_box else None,
                'combined_score': combined,
                'scores': indiv,
                'det_score': fd['det'],
            })

        # ─ Process HOG‑only persons (no face visible) ─
        used_hog = set()
        for fd in faces_raw:
            body_box = _estimate_body_from_face(fd['box'], frame.shape)
            if body_box and hog_boxes:
                for i, hb in enumerate(hog_boxes):
                    if _iou(body_box, hb) > 0.15:
                        used_hog.add(i)
        for i, hb in enumerate(hog_boxes):
            if i in used_hog:
                continue
            bx1, by1, bx2, by2 = hb
            bx1, by1 = max(0, bx1), max(0, by1)
            bx2, by2 = min(w - 1, bx2), min(h - 1, by2)
            if bx2 <= bx1 or by2 <= by1:
                continue
            pc = frame[by1:by2, bx1:bx2]
            if pc.size == 0:
                continue
            body_emb = self.osnet.encode(pc)
            clothing_feat = self.clothing.extract(pc)
            combined, indiv = self._score(body_emb=body_emb, clothing_feat=clothing_feat)
            if combined > 0:
                detections.append({
                    'face_box': None,
                    'body_box': [bx1, by1, bx2, by2],
                    'combined_score': combined,
                    'scores': indiv,
                    'det_score': 0.0,
                })

        detections.sort(key=lambda d: d['combined_score'], reverse=True)
        return detections

    # -----------------------------------------------------------
    # 4. Camera search loop
    # -----------------------------------------------------------
    def start_search(self, cam_id=0, output_dir=None, max_seconds=None):
        if self.searching:
            return False, "Search already running"
        if not any([self.ref_face_emb is not None, self.ref_body_emb is not None, self.ref_clothing_feat is not None]):
            return False, "Load a reference image first (set_reference)"

        self.output_dir = output_dir or self.output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self._stop = False
        self.searching = True
        self.status = "searching"
        self.matches = []
        self.best_match = None
        self._start_ts = time.time()

        ms = max_seconds or MAX_SEARCH_SECONDS
        self._thread = threading.Thread(target=self._loop, args=(cam_id, ms), daemon=True)
        self._thread.start()
        return True, f"Searching on camera {cam_id}..."

    def _loop(self, cam_id, max_sec):
        source = CAMERA_SOURCES.get(cam_id, 0)
        fc = 0
        try:
            while not self._stop:
                if time.time() - self._start_ts > max_sec:
                    self.status = "timeout"
                    break

                frame = camera_manager.get_latest_frame(source)
                if frame is None:
                    time.sleep(0.05)
                    continue

                fc += 1
                # Process every single frame for instantaneous detection (removed skip)


                dets = self.process_frame(frame)
                for det in dets:
                    score = det['combined_score']
                    if score < MATCH_THRESHOLD:
                        continue

                    result = self._save(frame, det, fc)
                    with self._lock:
                        self.matches.append(result)
                        if self.best_match is None or score > self.best_match['combined_score']:
                            self.best_match = result

                    if score >= CONFIDENT_THRESHOLD:
                        self.status = "found"
                        self.searching = False
                        logger.info("✅ PERSON FOUND  score=%.3f  path=%s", score, result['saved_path'])
                        return

                    if len(self.matches) >= SAVE_TOP_N:
                        self.status = "found"
                        self.searching = False
                        logger.info("✅ Top-%d matches collected", SAVE_TOP_N)
                        return

                time.sleep(0.02)
        except Exception as exc:
            logger.exception("Search loop error: %s", exc)
            self.status = "error"
        finally:
            self.searching = False
            if self.status == "searching":
                self.status = "found" if self.matches else "timeout"

    # -----------------------------------------------------------
    # 5. Save match to disk
    # -----------------------------------------------------------
    def _save(self, frame, det, frame_num):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        fname = f"match_{ts}_f{frame_num}_s{det['combined_score']:.2f}.jpg"
        path = os.path.join(self.output_dir, fname)

        vis = frame.copy()

        # Draw body box (cyan)
        if det.get('body_box'):
            bx1, by1, bx2, by2 = map(int, det['body_box'])
            cv2.rectangle(vis, (bx1, by1), (bx2, by2), (255, 200, 0), 2)

        # Draw face box (green)
        if det.get('face_box'):
            fx1, fy1, fx2, fy2 = map(int, det['face_box'])
            cv2.rectangle(vis, (fx1, fy1), (fx2, fy2), (0, 255, 0), 3)

        # Score label
        anchor = det.get('face_box') or det.get('body_box')
        if anchor:
            ax, ay = int(anchor[0]), int(anchor[1])
            cv2.putText(vis, f"MATCH {det['combined_score']:.2f}",
                        (ax, max(18, ay - 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2)
            # Individual score breakdown
            y_off = max(18, ay - 34)
            for k, v in det.get('scores', {}).items():
                cv2.putText(vis, f"{k}:{v:.2f}", (ax, y_off),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
                y_off -= 18

        cv2.imwrite(path, vis)

        # Also save clean (no annotations)
        clean = os.path.join(self.output_dir, f"clean_{fname}")
        cv2.imwrite(clean, frame)

        logger.info("Saved match: %s (score=%.3f)", path, det['combined_score'])

        return {
            'saved_path': path,
            'clean_path': clean,
            'combined_score': det['combined_score'],
            'scores': det.get('scores', {}),
            'face_box': det.get('face_box'),
            'body_box': det.get('body_box'),
            'frame_num': frame_num,
            'timestamp': ts,
        }

    # -----------------------------------------------------------
    # 6. Control helpers
    # -----------------------------------------------------------
    def stop_search(self):
        self._stop = True
        self.searching = False
        if self.status == "searching":
            self.status = "stopped"

    def get_status(self):
        with self._lock:
            return {
                'status': self.status,
                'searching': self.searching,
                'matches_found': len(self.matches),
                'best_match': self.best_match,
                'elapsed_sec': round(time.time() - self._start_ts, 1) if self._start_ts else 0,
                'features': {
                    'face': self.ref_face_emb is not None,
                    'body': self.ref_body_emb is not None,
                    'clothing': self.ref_clothing_feat is not None,
                },
            }

    def get_results(self):
        with self._lock:
            return {
                'status': self.status,
                'total': len(self.matches),
                'matches': list(self.matches),
                'best_match': self.best_match,
            }


# ═══════════════════════════════════════════════════════════════════
#  Singleton
# ═══════════════════════════════════════════════════════════════════
face_tracer = FaceTracer()
