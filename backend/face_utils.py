# backend/face_utils.py
import cv2
import onnxruntime as ort
import numpy as np
import os

_BASE_DIR = os.path.dirname(__file__)
_MODEL_PATH = os.path.join(_BASE_DIR, 'models', 'retinaface_mobilenet0.25.onnx')
if not os.path.exists(_MODEL_PATH):
    raise FileNotFoundError(f"RetinaFace model not found at {_MODEL_PATH}")

face_session = ort.InferenceSession(_MODEL_PATH, providers=["CPUExecutionProvider"])
input_name = face_session.get_inputs()[0].name

# Optional OpenCV DNN SSD (deploy.prototxt + res10_300x300_ssd_iter_140000.caffemodel) if user downloads them into models/
_DNN_PROTO = os.path.join(_BASE_DIR, 'models', 'deploy.prototxt')
_DNN_MODEL = os.path.join(_BASE_DIR, 'models', 'res10_300x300_ssd_iter_140000.caffemodel')
_dnn_net = None
if os.path.exists(_DNN_PROTO) and os.path.exists(_DNN_MODEL):
    try:
        _dnn_net = cv2.dnn.readNetFromCaffe(_DNN_PROTO, _DNN_MODEL)
    except Exception:
        _dnn_net = None

_HAAR_PATH = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
_haar_cascade = cv2.CascadeClassifier(_HAAR_PATH) if os.path.exists(_HAAR_PATH) else None

_ENABLE_DEBUG = os.getenv('FACE_DEBUG', '0') == '1'
_FORCE_HAAR = os.getenv('FORCE_HAAR', '0') == '1'
_ALLOW_CENTER_FB = os.getenv('ALLOW_CENTER_FALLBACK', '1') == '1'
_USE_DNN = os.getenv('USE_DNN_FACE', '0') == '1'  # force DNN

_DEF_MAX_BOXES = int(os.getenv('MAX_FACE_BOXES', '6'))

def _debug(msg):
    if _ENABLE_DEBUG:
        print(f"[FACE_DEBUG] {msg}")

def _nms(boxes, overlap=0.45):
    if not boxes:
        return []
    boxes_np = np.array(boxes, dtype=np.float32)
    x1 = boxes_np[:,0]; y1 = boxes_np[:,1]; x2 = boxes_np[:,2]; y2 = boxes_np[:,3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = areas.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        inds = np.where(iou <= overlap)[0]
        order = order[inds + 1]
    return [boxes[idx] for idx in keep]

def _retinaface_try(frame):
    if _FORCE_HAAR or _USE_DNN:
        return []
    try:
        h0, w0 = frame.shape[:2]
        img = cv2.resize(frame, (640, 640))
        img_input = img.transpose(2,0,1)[None].astype(np.float32)
        outs = face_session.run(None, {input_name: img_input})
        cand = None
        for o in outs:
            arr = np.array(o)
            if arr.ndim == 3 and arr.shape[0] == 1 and arr.shape[2] >= 5:
                cand = arr[0]; break
            if arr.ndim == 2 and arr.shape[1] >= 5:
                cand = arr; break
        if cand is None:
            return []
        boxes = []
        for p in cand:
            if p.shape[0] < 5: continue
            score = p[4]
            if score < 0.6: continue
            coords = p[:4]
            x1=y1=x2=y2=None
            if coords.max() <= 1.5: # normalized
                cx, cy, w, h = coords * 640
                x1 = int((cx - w/2) * w0 / 640)
                y1 = int((cy - h/2) * h0 / 640)
                x2 = int((cx + w/2) * w0 / 640)
                y2 = int((cy + h/2) * h0 / 640)
            elif coords.max() <= 642:
                cx, cy, w, h = coords
                x1 = int((cx - w/2) * w0 / 640)
                y1 = int((cy - h/2) * h0 / 640)
                x2 = int((cx + w/2) * w0 / 640)
                y2 = int((cy + h/2) * h0 / 640)
            else:
                x1, y1, x2, y2 = coords
            if None in (x1,y1,x2,y2): continue
            if x2 <= x1 or y2 <= y1: continue
            boxes.append([int(x1), int(y1), int(x2), int(y2)])
        if boxes:
            boxes = _nms(boxes, 0.4)
        # Heuristic: if too many boxes treat as failure
        if len(boxes) > _DEF_MAX_BOXES:
            _debug(f"RetinaFace produced {len(boxes)} boxes > limit; dropping")
            return []
        if boxes:
            _debug(f"RetinaFace boxes: {len(boxes)}")
        return boxes
    except Exception as e:
        _debug(f"RetinaFace fail: {e}")
        return []

def _dnn_faces(frame):
    if _dnn_net is None:
        return []
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300,300), (104,177,123))
    _dnn_net.setInput(blob)
    dets = _dnn_net.forward()
    boxes = []
    for i in range(dets.shape[2]):
        conf = dets[0,0,i,2]
        if conf < 0.55:
            continue
        x1 = int(dets[0,0,i,3] * w)
        y1 = int(dets[0,0,i,4] * h)
        x2 = int(dets[0,0,i,5] * w)
        y2 = int(dets[0,0,i,6] * h)
        if x2 <= x1 or y2 <= y1: continue
        boxes.append([x1,y1,x2,y2])
    if boxes:
        boxes = _nms(boxes, 0.4)
        _debug(f"DNN boxes: {len(boxes)}")
    return boxes

def detect_faces(frame):
    boxes = []
    if _USE_DNN:
        boxes = _dnn_faces(frame)
    else:
        boxes = _retinaface_try(frame)
    if (not boxes) and _haar_cascade is not None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _haar_cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=4, minSize=(60,60))
        for (x,y,w,h) in faces:
            boxes.append([int(x), int(y), int(x+w), int(y+h)])
        if boxes:
            boxes = _nms(boxes, 0.4)
            _debug(f"Haar boxes: {len(boxes)}")
    if (not boxes) and _ALLOW_CENTER_FB:
        h, w = frame.shape[:2]
        cw, ch = int(w*0.28), int(h*0.28)
        x1 = w//2 - cw//2; y1 = h//2 - ch//2
        boxes = [[x1,y1,x1+cw,y1+ch]]
        _debug('Center fallback injected')
    return boxes[:_DEF_MAX_BOXES]
