# action_engine.py
from typing import Dict, Any, List

# Support running both as package (backend.*) and as plain script from backend/ dir
try:
    from .utils_pose_rules import classify_action, DEFAULT_PARAMS  # type: ignore
except ImportError:  # fallback when relative context missing
    from utils_pose_rules import classify_action, DEFAULT_PARAMS  # type: ignore

def iou(boxA, boxB):
    xA = max(boxA[0], boxB[0]); yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2]); yB = min(boxA[3], boxB[3])
    inter_w = max(0, xB - xA)
    inter_h = max(0, yB - yA)
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0
    areaA = (boxA[2]-boxA[0])*(boxA[3]-boxA[1])
    areaB = (boxB[2]-boxB[0])*(boxB[3]-boxB[1])
    denom = areaA + areaB - inter + 1e-6
    return inter/denom if denom>0 else 0.0

# Enhanced weapon association scoring
# weapon_score combines: IoU, center containment (with margin) and proximity
# This helps when detector gives a small gun box just outside the person box edge.

def classify(person_track: Dict[str, Any], pose, prev_pose, weapon_detections: List[List[float]]):
    pb = person_track['bbox']
    pbox = (pb[0],pb[1],pb[2],pb[3])
    px_c = (pbox[0]+pbox[2])/2.0
    py_c = (pbox[1]+pbox[3])/2.0
    pw = max(1.0, pbox[2]-pbox[0])
    ph = max(1.0, pbox[3]-pbox[1])

    best_score = 0.0
    for det in weapon_detections:
        if len(det) < 6:
            continue
        wx1,wy1,wx2,wy2,conf,_ = det
        if conf <= 0:
            continue
        wb = (wx1,wy1,wx2,wy2)
        w_iou = iou(pbox, wb)
        # Center containment with margin
        wx_c = (wx1+wx2)/2.0
        wy_c = (wy1+wy2)/2.0
        margin = 0.20  # 20% expansion
        x_min_exp = pbox[0] - pw*margin
        x_max_exp = pbox[2] + pw*margin
        y_min_exp = pbox[1] - ph*margin
        y_max_exp = pbox[3] + ph*margin
        inside = (x_min_exp <= wx_c <= x_max_exp) and (y_min_exp <= wy_c <= y_max_exp)
        # Proximity (normalized distance of centers)
        dx = (wx_c - px_c)/pw
        dy = (wy_c - py_c)/ph
        center_dist = (dx*dx + dy*dy) ** 0.5  # normalized
        proximity_score = max(0.0, 1.0 - center_dist / 0.75)  # fade out after ~0.75 norm distance
        # IoU emphasis curve
        iou_component = 0.5 + 0.5*min(1.0, w_iou*4.0)
        containment_component = 1.0 if inside else 0.0
        composite = max(iou_component, containment_component, proximity_score)
        score_candidate = conf * composite
        if score_candidate > best_score:
            best_score = score_candidate
    weapon_score = best_score
    action = classify_action(pose, prev_pose, person_track, weapon_score, DEFAULT_PARAMS)
    return action, weapon_score
