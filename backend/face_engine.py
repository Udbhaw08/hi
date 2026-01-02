# backend/face_engine.py
import os
from functools import lru_cache
import cv2
from insightface.app import FaceAnalysis

_ENABLE = os.getenv('USE_INSIGHTFACE', '1') == '1'
# Choose pack: antelopev2 includes SCRFD + glintr100 (fast & accurate)
_DEFAULT_PACK = os.getenv('INSIGHTFACE_MODEL', 'antelopev2')
_DET_SIZE_ENV = os.getenv('INSIGHTFACE_DET_SIZE', '512x512')
try:
    _dw,_dh = _DET_SIZE_ENV.lower().split('x')
    _DET_SIZE = (int(_dw), int(_dh))
except Exception:
    _DET_SIZE = (512,512)
_FORCE_CPU = os.getenv('FORCE_CPU','0')=='1'

# Provider list (prefer CUDA, then DirectML, fallback CPU)
_providers = ['CPUExecutionProvider']
try:
    import onnxruntime as ort  # noqa
    av = ort.get_available_providers()
    if not _FORCE_CPU:
        for cand in ('CUDAExecutionProvider','DmlExecutionProvider'):
            if cand in av:
                _providers = [cand,'CPUExecutionProvider']
                break
except Exception:
    pass

@lru_cache(maxsize=1)
def _get_app():
    if not _ENABLE:
        raise RuntimeError('InsightFace disabled via USE_INSIGHTFACE=0')
    app = FaceAnalysis(name=_DEFAULT_PACK, providers=_providers)
    # ctx_id=0 uses first GPU when CUDAExecutionProvider present
    app.prepare(ctx_id=0, det_size=_DET_SIZE)
    return app

# Returns list of ((x1,y1,x2,y2), embedding(numpy float32 normed), det_score)
def detect_and_embed(bgr):
    app = _get_app()
    faces = app.get(bgr)
    out = []
    for f in faces:
        box = f.bbox.astype(int)
        x1,y1,x2,y2 = box
        if (x2-x1) < 40 or (y2-y1) < 40:  # tighter min size for speed/quality
            continue
        emb = f.normed_embedding
        out.append(((int(x1),int(y1),int(x2),int(y2)), emb.astype('float32'), float(getattr(f,'det_score',0.0))))
    return out
