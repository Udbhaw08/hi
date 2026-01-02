# backend/compute_embeddings.py
import onnxruntime as ort
import cv2
import numpy as np
import os
from .db import person_collection

_BASE_DIR = os.path.dirname(__file__)
_MODEL_PATH = os.path.join(_BASE_DIR, 'models', 'arcface_r100.onnx')
if not os.path.exists(_MODEL_PATH):
    raise FileNotFoundError(f"ArcFace model not found at {_MODEL_PATH}")

session = ort.InferenceSession(_MODEL_PATH, providers=["CPUExecutionProvider"])
input_name = session.get_inputs()[0].name

for person in person_collection.find():
    path = person.get("image_path")
    if not path:
        continue
    img = cv2.imread(path)
    if img is None:
        continue
    img = cv2.resize(img, (112, 112))
    img_input = img.transpose(2,0,1)[None].astype(np.float32)
    img_input = (img_input - 127.5) / 128.0
    embedding = session.run(None, {input_name: img_input})[0][0]
    # Normalize
    norm = np.linalg.norm(embedding)
    if norm == 0:
        continue
    embedding = (embedding / norm).tolist()
    person_collection.update_one({"_id": person["_id"]}, {"$set": {"embedding": embedding}})
