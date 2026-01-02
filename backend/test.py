# test.py — YOLOv8 ONNX live demo (webcam)

import cv2
import onnxruntime as ort
import numpy as np
import os
import sys

# -----------------------------
# 1️⃣ Paths & settings
# -----------------------------
# Use repo-relative path instead of hard-coded absolute (previous path missed 'SIH')
MODEL_FILENAME = 'best.onnx'
model_path = os.path.join(os.path.dirname(__file__), 'models', MODEL_FILENAME)
input_size = 640          # YOLOv8 training size
conf_threshold = 0.25     # Confidence threshold for class probability
iou_threshold = 0.45      # NMS IoU threshold

# Insert debug/env based configuration additions
SWAP_GUN_KNIFE = os.getenv('SWAP_GUN_KNIFE','0')=='1'
APPLY_SIGMOID = os.getenv('APPLY_CLASS_SIGMOID','0')=='1'
PER_CLASS_DEBUG = os.getenv('PER_CLASS_DEBUG','0')=='1'

classes = ["person", "gun", "knife"]  # ordered exactly as trained
if SWAP_GUN_KNIFE and len(classes)==3:
    # Quick test if export swapped order internally (person, knife, gun)
    classes = [classes[0], classes[2], classes[1]]
    print('[INFO] SWAP_GUN_KNIFE=1 -> using class order:', classes)

if not os.path.exists(model_path):
    print(f"[ERROR] Model file not found at: {model_path}")
    print("Place the exported ONNX file under backend/models/best.onnx")
    sys.exit(1)

# -----------------------------
# 2️⃣ Initialize ONNX Runtime session
# -----------------------------
available = ort.get_available_providers()
preferred_order = ['CUDAExecutionProvider', 'DmlExecutionProvider', 'AzureExecutionProvider', 'CPUExecutionProvider']
providers = [p for p in preferred_order if p in available]
print("Available providers:", available)
print("Using providers:", providers)

try:
    session = ort.InferenceSession(model_path, providers=providers)
except Exception as e:
    print(f"[FATAL] Could not create inference session: {e}")
    sys.exit(1)

input_name = session.get_inputs()[0].name

# -----------------------------
# 3️⃣ Helper functions
# -----------------------------

def letterbox(img, new_size=(640, 640), color=(114, 114, 114)):
    h, w = img.shape[:2]
    scale = min(new_size[0]/w, new_size[1]/h)
    nw, nh = int(w*scale), int(h*scale)
    img_resized = cv2.resize(img, (nw, nh))
    new_img = np.full((new_size[1], new_size[0], 3), color, dtype=np.uint8)
    top = (new_size[1]-nh)//2
    left = (new_size[0]-nw)//2
    new_img[top:top+nh, left:left+nw] = img_resized
    return new_img, scale, (left, top)

def xywh2xyxy(x):
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2]/2
    y[:, 1] = x[:, 1] - x[:, 3]/2
    y[:, 2] = x[:, 0] + x[:, 2]/2
    y[:, 3] = x[:, 1] + x[:, 3]/2
    return y

def bbox_iou(box1, boxes2):
    x1 = np.maximum(box1[0], boxes2[:,0])
    y1 = np.maximum(box1[1], boxes2[:,1])
    x2 = np.minimum(box1[2], boxes2[:,2])
    y2 = np.minimum(box1[3], boxes2[:,3])
    inter = np.maximum(0, x2-x1) * np.maximum(0, y2-y1)
    area1 = (box1[2]-box1[0])*(box1[3]-box1[1])
    area2 = (boxes2[:,2]-boxes2[:,0])*(boxes2[:,3]-boxes2[:,1])
    return inter / (area1 + area2 - inter + 1e-6)

def nms(boxes, scores, iou_threshold):
    idxs = scores.argsort()[::-1]
    keep = []
    while len(idxs) > 0:
        i = idxs[0]
        keep.append(i)
        if len(idxs) == 1:
            break
        ious = bbox_iou(boxes[i], boxes[idxs[1:]])
        idxs = idxs[1:][ious < iou_threshold]
    return keep

# -----------------------------
# 4️⃣ Webcam loop
# -----------------------------
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print('[ERROR] Cannot open webcam index 0')
    sys.exit(1)

print('[INFO] Press ESC to exit')

while True:
    ret, frame = cap.read()
    if not ret:
        print('[WARN] Frame grab failed, exiting')
        break

    img_lb, scale, pad = letterbox(frame, (input_size, input_size))
    img_in = img_lb[:, :, ::-1].transpose(2,0,1)  # BGR->RGB, HWC->CHW
    img_in = np.ascontiguousarray(img_in, dtype=np.float32) / 255.0
    img_in = np.expand_dims(img_in, axis=0)

    # ONNX inference
    outputs = session.run(None, {input_name: img_in})
    raw = outputs[0]  # expected shape: (1, 7, 8400)
    if raw.ndim != 3:
        print(f"[ERROR] Unexpected output shape: {raw.shape}")
        break
    raw = np.squeeze(raw, axis=0)          # (7, 8400)
    raw = raw.transpose(1, 0)              # (8400, 7)

    if raw.shape[1] != (4 + len(classes)):
        print(f"[ERROR] Channel mismatch. Got {raw.shape[1]} expected {4+len(classes)}")
        break

    boxes_xywh = raw[:, :4]
    class_scores = raw[:, 4:]              # (8400, num_classes)
    if APPLY_SIGMOID:
        # Only if export lacked activation; usually NOT needed. Enabled via env.
        class_scores = 1.0 / (1.0 + np.exp(-class_scores))

    # Get best class per anchor
    class_ids = np.argmax(class_scores, axis=1)
    confidences = class_scores[np.arange(class_scores.shape[0]), class_ids]

    # Threshold
    mask = confidences >= conf_threshold
    boxes_xywh = boxes_xywh[mask]
    confidences = confidences[mask]
    class_ids = class_ids[mask]

    if boxes_xywh.size > 0:
        boxes_xyxy = xywh2xyxy(boxes_xywh)
        # Scale boxes back to original frame
        # Undo letterbox: subtract pad then divide by scale
        left, top = pad
        boxes_xyxy[:, [0,2]] -= left
        boxes_xyxy[:, [1,3]] -= top
        boxes_xyxy /= scale

        # Clip to frame
        h0, w0 = frame.shape[:2]
        boxes_xyxy[:, 0] = np.clip(boxes_xyxy[:, 0], 0, w0-1)
        boxes_xyxy[:, 1] = np.clip(boxes_xyxy[:, 1], 0, h0-1)
        boxes_xyxy[:, 2] = np.clip(boxes_xyxy[:, 2], 0, w0-1)
        boxes_xyxy[:, 3] = np.clip(boxes_xyxy[:, 3], 0, h0-1)

        # NMS (class-agnostic). For class-wise, group by class.
        keep = nms(boxes_xyxy, confidences, iou_threshold)
        boxes_xyxy = boxes_xyxy[keep]
        confidences = confidences[keep]
        class_ids = class_ids[keep]

        for det_i, ((x1, y1, x2, y2), conf, cid) in enumerate(zip(boxes_xyxy.astype(int), confidences, class_ids)):
            label = f"{classes[cid]} {conf:.2f}"
            color = (0,0,255) if classes[cid] in ('gun','knife') else (0,255,0)
            cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
            cv2.putText(frame, label, (x1, max(15,y1-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
            if PER_CLASS_DEBUG and det_i < 10:
                probs = class_scores[det_i]
                pcs = ' '.join([f"{classes[i]}:{probs[i]:.2f}" for i in range(len(classes))])
                print(f"[DBG] det#{det_i} {x1},{y1},{x2},{y2} -> {pcs}")

    cv2.imshow("YOLOv8 ONNX Demo", frame)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()
