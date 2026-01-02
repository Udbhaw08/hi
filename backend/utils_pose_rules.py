# utils_pose_rules.py
import os
import numpy as np
from collections import deque

# Tunable parameters (override via env e.g. AIM_ANGLE_MIN=135)
DEFAULT_PARAMS = {
    'aim_angle_min': float(os.getenv('AIM_ANGLE_MIN', '140')),      # straighter arm min elbow angle (stricter)
    'aim_arm_extend_min': float(os.getenv('AIM_EXTEND_MIN', '0.10')),
    'aim_wrist_raise_min': float(os.getenv('AIM_WRIST_RAISE_MIN', '0.06')),
    'loiter_duration_sec': float(os.getenv('LOITER_DURATION', '8.0')),
    'loiter_radius_px': float(os.getenv('LOITER_RADIUS_PX', '40')),
    'running_speed_px': float(os.getenv('RUN_SPEED_PX', '360')),
    'fight_wrist_vel_norm': float(os.getenv('FIGHT_WRIST_VEL', '0.12')),
    # Lower threshold so any reasonably confident nearby weapon flags user.
    'weapon_iou_min': float(os.getenv('WEAPON_IOU_MIN', '0.02')),
    'weapon_score_min': float(os.getenv('WEAPON_SCORE_MIN', '0.20')),  # slightly higher
    'pose_history_len': int(os.getenv('POSE_HISTORY_LEN','5')),
}

# BlazePose indices (33 keypoints). Only need arms for now.
LS, RS, LE, RE, LW, RW = 11, 12, 13, 14, 15, 16

def _elbow_angle(shoulder, elbow, wrist):
    try:
        a = np.array(shoulder[:2]); b = np.array(elbow[:2]); c = np.array(wrist[:2])
        ba = a - b; bc = c - b
        cosang = (ba @ bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
        return np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0)))
    except Exception:
        return 0.0

def detect_aiming(pose, params):
    if pose is None: return False
    try:
        right_angle = _elbow_angle(pose[RS], pose[RE], pose[RW])
        left_angle  = _elbow_angle(pose[LS], pose[LE], pose[LW])
        rs, rw = pose[RS], pose[RW]; ls, lw = pose[LS], pose[LW]
        right_extend = abs(rw[0] - rs[0]); left_extend = abs(lw[0] - ls[0])
        right_raise = rs[1] - rw[1]; left_raise = ls[1] - lw[1]  # y smaller is higher
        cond_r = (right_angle >= params['aim_angle_min'] and (right_extend >= params['aim_arm_extend_min'] or right_raise >= params['aim_wrist_raise_min']))
        cond_l = (left_angle  >= params['aim_angle_min'] and (left_extend  >= params['aim_arm_extend_min'] or left_raise  >= params['aim_wrist_raise_min']))
        return cond_r or cond_l
    except Exception:
        return False

def aiming_metrics(pose):
    if pose is None:
        return {}
    try:
        right_angle = _elbow_angle(pose[RS], pose[RE], pose[RW])
        left_angle  = _elbow_angle(pose[LS], pose[LE], pose[LW])
        rs, rw = pose[RS], pose[RW]; ls, lw = pose[LS], pose[LW]
        return {
            'right_angle': right_angle,
            'left_angle': left_angle,
            'right_extend': abs(rw[0]-rs[0]),
            'left_extend':  abs(lw[0]-ls[0]),
            'right_raise':  rs[1]-rw[1],
            'left_raise':   ls[1]-lw[1]
        }
    except Exception:
        return {}

def _path_radius(history):
    if len(history) < 5: return 0.0
    xs = [p[0] for p in history]; ys = [p[1] for p in history]
    return max(np.ptp(xs), np.ptp(ys))

def is_loitering(track, params):
    hist = track.get('history')
    if not hist or len(hist) < 25:  # require more data (~>1s)
        return False
    dur = track.get('last_ts',0) - track.get('first_ts',0)
    if dur < params['loiter_duration_sec']:
        return False
    return _path_radius(hist) <= params['loiter_radius_px']

def wrist_velocity(prev_pose, curr_pose):
    try:
        if prev_pose is None or curr_pose is None: return 0.0, 0.0
        rw_prev = np.array(prev_pose[RW][:2]); rw_cur = np.array(curr_pose[RW][:2])
        lw_prev = np.array(prev_pose[LW][:2]); lw_cur = np.array(curr_pose[LW][:2])
        return np.linalg.norm(rw_cur - rw_prev), np.linalg.norm(lw_cur - lw_prev)
    except Exception:
        return 0.0, 0.0

def _smoothed_wrist_velocity_from_history(pose_history):
    """Compute average wrist velocity over consecutive pose pairs in history."""
    if not pose_history or len(pose_history) < 2:
        return 0.0, 0.0
    rv_total = 0.0; lv_total = 0.0; cnt = 0
    for i in range(1, len(pose_history)):
        p0 = pose_history[i-1]; p1 = pose_history[i]
        if p0 is None or p1 is None: continue
        rv, lv = wrist_velocity(p0, p1)
        rv_total += rv; lv_total += lv; cnt += 1
    if cnt == 0: return 0.0, 0.0
    return rv_total / cnt, lv_total / cnt

def is_fighting(prev_pose, curr_pose, params):
    # keep backward-compatible signature (single-frame) but prefer using history if available
    rv, lv = wrist_velocity(prev_pose, curr_pose)
    return (rv > params['fight_wrist_vel_norm']) or (lv > params['fight_wrist_vel_norm'])

def classify_action(pose, prev_pose, track, weapon_score, params=DEFAULT_PARAMS):
    # Precedence: Aiming > Weapon > Loitering > Running > Fighting > Normal
    # Use smoothed pose history if available on track to reduce noise
    pose_hist = None
    try:
        pose_hist = track.get('pose_history') if track is not None else None
    except Exception:
        pose_hist = None

    # Weapon checks
    if weapon_score >= params['weapon_score_min']:
        if pose is not None and detect_aiming(pose, params):
            return 'Aiming'
        return 'Weapon'

    # Loitering
    if is_loitering(track, params):
        return 'Loitering'

    # Running: rely on tracker speed smoothing if available
    sp_deque = track.get('speeds') if track is not None else None
    if sp_deque and len(sp_deque) >= 3:
        avg_sp = sum(sp_deque)/len(sp_deque)
        if avg_sp >= params['running_speed_px']:
            return 'Running'

    # Fighting: use smoothed wrist velocity over history if present
    if pose_hist:
        rv_avg, lv_avg = _smoothed_wrist_velocity_from_history(list(pose_hist))
        if (rv_avg > params['fight_wrist_vel_norm']) or (lv_avg > params['fight_wrist_vel_norm']):
            return 'Fighting'
    else:
        if pose is not None and prev_pose is not None and is_fighting(prev_pose, pose, params):
            return 'Fighting'

    return 'Normal'

# Backward compatibility names
is_raising_or_aiming = detect_aiming
