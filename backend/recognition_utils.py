# recognition_utils.py
import numpy as np
import cv2
import onnxruntime as ort
from typing import Optional, Dict, Any
import os
import glob
from .db import person_collection
from .config import MATCH_THRESHOLD

# Provider auto-detection: prefer CUDA > DirectML > CPU
_PROVIDERS = ['CPUExecutionProvider']
try:
    _av = ort.get_available_providers()
    for _cand in ('CUDAExecutionProvider', 'DmlExecutionProvider'):
        if _cand in _av:
            _PROVIDERS = [_cand, 'CPUExecutionProvider']
            break
except Exception:
    pass
print(f"[recognition_utils] Using provider: {_PROVIDERS[0]}")

_BASE_DIR = os.path.dirname(__file__)
_ARCFACE_PRI = os.path.join(_BASE_DIR, 'models', 'glintr100.onnx')  # Using available glintr100.onnx model
_ARCFACE_FALLBACK = os.path.join(_BASE_DIR, 'models', 'best.onnx')  # Using available best.onnx as fallback
_AVAILABLE_MODELS = [m for m in [os.path.basename(_ARCFACE_PRI), os.path.basename(_ARCFACE_FALLBACK)] if os.path.exists(os.path.join(_BASE_DIR, 'models', m))]

_model_path_loaded: Optional[str] = None
_last_infer_error: Optional[str] = None
_fallback_used = False

_embedding_cache: Dict[str, Dict[str, Any]] = {}
# Vectorized structures
_emb_matrix = None  # numpy ndarray (N,D)
_pid_list = []      # list of person_ids in same order as rows
_doc_list = []      # list of docs

_arcface_session: Optional[ort.InferenceSession] = None

import os as _os  # ensure env access for fallback toggle
ALLOW_PSEUDO_EMB = _os.getenv('ALLOW_PSEUDO_EMB', '1') == '1'

_LOCAL_IMG_DIR = os.path.join(_BASE_DIR, '..', 'data', 'person_images')
_local_img_embeds = {}  # person_id -> embedding (numpy)
LOCAL_IMG_THRESHOLD = float(os.getenv('LOCAL_IMG_THRESHOLD', '0.40'))


def _load_session(path: str):
    global _model_path_loaded
    sess = ort.InferenceSession(path, providers=_PROVIDERS)
    _model_path_loaded = path
    return sess


def _init_model():
    global _arcface_session, _fallback_used, _last_infer_error
    if os.path.exists(_ARCFACE_PRI):
        try:
            _arcface_session = _load_session(_ARCFACE_PRI)
            _fallback_used = False
            return
        except Exception as e:
            _last_infer_error = f"Primary load fail: {e}"
    if os.path.exists(_ARCFACE_FALLBACK):
        _arcface_session = _load_session(_ARCFACE_FALLBACK)
        _fallback_used = True
    else:
        raise FileNotFoundError("No ArcFace model (.onnx) found.")


def switch_model(target: str):
    global _arcface_session, _fallback_used, _last_infer_error
    path = _ARCFACE_PRI if target == 'r100' else _ARCFACE_FALLBACK if target == 'mobile' else None
    if path is None:
        raise ValueError("target must be 'r100' or 'mobile'")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model file not found: {path}")
    try:
        _arcface_session = _load_session(path)
        _fallback_used = (target != 'r100')
        _last_infer_error = None
        return True
    except Exception as e:
        _last_infer_error = f"Switch fail: {e}"
        return False


_init_model()
_input_name = _arcface_session.get_inputs()[0].name  # type: ignore
_input_shape = _arcface_session.get_inputs()[0].shape  # type: ignore


def _preprocess_face(bgr_img):
    if bgr_img is None or bgr_img.size == 0:
        return None
    img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (112, 112))
    img = img.astype(np.float32)
    img = (img - 127.5) / 128.0
    img = img.transpose(2, 0, 1)
    img = np.ascontiguousarray(img)
    return img[None]


def compute_embedding(face_bgr) -> Optional[np.ndarray]:
    global _last_infer_error, _fallback_used
    try:
        blob = _preprocess_face(face_bgr)
        if blob is None:
            return None
        emb = _arcface_session.run(None, {_input_name: blob})[0]  # type: ignore
        emb = np.squeeze(emb)
        norm = np.linalg.norm(emb)
        if norm == 0:
            return None
        return (emb / norm).astype(np.float32)
    except Exception as e:
        _last_infer_error = f"Inference fail on {os.path.basename(_model_path_loaded or '')}: {e}"
        if not _fallback_used and os.path.exists(_ARCFACE_FALLBACK):
            if switch_model('mobile'):
                try:
                    blob = _preprocess_face(face_bgr)
                    if blob is None:
                        return None
                    emb = _arcface_session.run(None, {_input_name: blob})[0]  # type: ignore
                    emb = np.squeeze(emb)
                    norm = np.linalg.norm(emb)
                    if norm == 0:
                        return None
                    return (emb / norm).astype(np.float32)
                except Exception as e2:
                    _last_infer_error = f"Fallback inference fail: {e2}"
        # Pseudo embedding fallback (to allow system to operate) ----------------
        if ALLOW_PSEUDO_EMB and face_bgr is not None and face_bgr.size > 0:
            try:
                small = cv2.resize(face_bgr, (32,32))  # 32x32x3
                hist = []
                # simple color hist (8 bins/channel)
                for ch in range(3):
                    hch = cv2.calcHist([small],[ch],None,[8],[0,256]).flatten()
                    hist.append(hch)
                vec = np.concatenate(hist)  # length 24
                # augment with mean/std per channel
                means = small.mean(axis=(0,1))
                stds = small.std(axis=(0,1)) + 1e-6
                extra = np.concatenate([means, stds])  # 6
                raw = np.concatenate([vec, extra])  # 30 dims
                # tile to ~480 then pad to 512
                reps = 512 // raw.size + 1
                tiled = np.tile(raw, reps)[:512]
                norm = np.linalg.norm(tiled)
                if norm == 0:
                    return None
                pseudo = (tiled / norm).astype(np.float32)
                if _last_infer_error:
                    print(f"[WARN] Using pseudo embedding due to failure: {_last_infer_error}")
                return pseudo
            except Exception as e3:
                _last_infer_error = f"Pseudo embedding generation failed: {e3}"  # final failure
        return None


def _rebuild_matrix():
    global _emb_matrix, _pid_list, _doc_list
    if not _embedding_cache:
        _emb_matrix = None
        _pid_list = []
        _doc_list = []
        return
    rows = []
    _pid_list = []
    _doc_list = []
    for pid, entry in _embedding_cache.items():
        rows.append(entry['embedding'])
        _pid_list.append(pid)
        _doc_list.append(entry['doc'])
    _emb_matrix = np.vstack(rows).astype(np.float32)


def load_local_image_embeddings():
    """Scan data/person_images for files named <person_id>.<ext> and compute embeddings.
    Stores embeddings in _local_img_embeds keyed by string person_id.
    """
    global _local_img_embeds
    _local_img_embeds = {}
    pattern = os.path.join(os.path.dirname(__file__), '..', 'data', 'person_images', '*')
    for path in glob.glob(pattern):
        try:
            base = os.path.basename(path)
            name, _ = os.path.splitext(base)
            person_id = name
            img = cv2.imread(path)
            if img is None:
                continue
            emb = compute_embedding(img)
            if emb is None:
                continue
            _local_img_embeds[person_id] = emb
        except Exception:
            continue


def compare_to_local_image(person_id: str, embedding: Optional[np.ndarray]):
    """Return cosine similarity between embedding and local image embedding for person_id if present.
    Returns None if no local image embedding exists or embedding is None.
    """
    if embedding is None:
        return None
    emb_local = _local_img_embeds.get(str(person_id))
    if emb_local is None:
        return None
    # cosine since normalized
    n = np.linalg.norm(embedding)
    if n == 0:
        return None
    emb = embedding / n
    score = float(np.dot(emb, emb_local))
    return score


def find_best_local_match(embedding: Optional[np.ndarray]):
    """Compare embedding to all locally stored person images and return best (person_id, score).
    Returns (None, None) if no local images or embedding is None.
    """
    if embedding is None:
        return None, None
    if not _local_img_embeds:
        return None, None
    n = np.linalg.norm(embedding)
    if n == 0:
        return None, None
    emb = embedding / n
    best_pid = None
    best_score = -1.0
    for pid, lemb in _local_img_embeds.items():
        s = float(np.dot(emb, lemb))
        if s > best_score:
            best_score = s; best_pid = pid
    return best_pid, best_score


def load_embedding_cache():
    global _embedding_cache
    _embedding_cache = {}
    for doc in person_collection.find({"embedding": {"$type": "array"}}):
        emb = np.array(doc["embedding"], dtype=np.float32).reshape(-1)
        norm = np.linalg.norm(emb)
        if norm == 0:
            continue
        emb = emb / norm
        _embedding_cache[doc["person_id"]] = {"embedding": emb, "doc": doc}
    _rebuild_matrix()
    # load local image embeddings as well
    try:
        load_local_image_embeddings()
    except Exception:
        pass
    print(f"[INFO] Loaded embeddings: {len(_embedding_cache)} persons (model: {os.path.basename(_model_path_loaded or '')})")


def add_person_embedding_to_cache(doc):
    if "embedding" not in doc or not isinstance(doc["embedding"], list):
        return
    emb = np.array(doc["embedding"], dtype=np.float32).reshape(-1)
    norm = np.linalg.norm(emb)
    if norm == 0:
        return
    emb = emb / norm
    _embedding_cache[doc["person_id"]] = {"embedding": emb, "doc": doc}
    _rebuild_matrix()


def match_face(embedding: np.ndarray):
    # embedding assumed normalized
    global _emb_matrix, _pid_list, _doc_list
    if embedding is None:
        return None, None
    if _emb_matrix is None or _emb_matrix.shape[0] == 0:
        return None, None
    # ensure normalized
    n = np.linalg.norm(embedding)
    if n == 0:
        return None, None
    emb = embedding / n
    # vectorized cosine (dot since normalized)
    scores = emb @ _emb_matrix.T  # shape (N,)
    idx = int(np.argmax(scores))
    best_score = float(scores[idx])
    if best_score >= MATCH_THRESHOLD:
        return _doc_list[idx], best_score
    return None, best_score


def model_status():
    return {
        "model_loaded": os.path.basename(_model_path_loaded or ''),
        "using_fallback": _fallback_used,
        "input_name": _input_name,
        "input_shape": _input_shape,
        "cache_size": len(_embedding_cache),
        "last_error": _last_infer_error,
        "available_models": _AVAILABLE_MODELS,
    }

def last_error():
    return _last_infer_error
