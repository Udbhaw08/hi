# bytetracker_utils.py
import time
from collections import deque
import numpy as np

class SimpleTracker:
    # Stores per-track: bbox(x1,y1,x2,y2,age), first_ts, last_ts, history[(cx,cy,ts)], speeds[pixels/sec]
    def __init__(self, max_age=30, history_len=120):
        self.next_id = 0
        self.tracks = {}
        self.max_age = max_age
        self.history_len = history_len

    def update(self, detections, now_ts=None):
        if now_ts is None:
            now_ts = time.time()
        updated = {}
        # age existing
        for tid, tr in list(self.tracks.items()):
            tr['bbox'] = (*tr['bbox'][:4], tr['bbox'][4] + 1)
            if tr['bbox'][4] > self.max_age:
                continue
        # match (greedy IoU)
        for det in detections:
            if len(det) < 6:
                continue
            x1,y1,x2,y2,conf,cls_id = det
            best_tid = None; best_iou = 0.0
            for tid, tr in self.tracks.items():
                tx1,ty1,tx2,ty2,_ = tr['bbox']
                iou = self._iou((x1,y1,x2,y2),(tx1,ty1,tx2,ty2))
                if iou > 0.3 and iou > best_iou:
                    best_iou = iou; best_tid = tid
            if best_tid is None:
                tid = self.next_id; self.next_id += 1
                updated[tid] = {
                    'bbox': (x1,y1,x2,y2,0),
                    'first_ts': now_ts,
                    'last_ts': now_ts,
                    'history': deque(maxlen=self.history_len),
                    'speeds': deque(maxlen=40)
                }
            else:
                tr = self.tracks[best_tid]
                tr['bbox'] = (x1,y1,x2,y2,0)
                tr['last_ts'] = now_ts
                updated[best_tid] = tr
            # history & speed
            tid_use = best_tid if best_tid is not None else (self.next_id - 1)
            trk = updated[tid_use]
            cx = (x1+x2)/2.0; cy = (y1+y2)/2.0
            hist = trk['history']
            if hist:
                px,py,pts = hist[-1]
                dt = max(1e-3, now_ts-pts)
                sp = np.hypot(cx-px, cy-py)/dt
                trk['speeds'].append(sp)
            hist.append((cx,cy,now_ts))
        self.tracks = updated
        return updated

    def _iou(self, a, b):
        xA = max(a[0], b[0]); yA = max(a[1], b[1])
        xB = min(a[2], b[2]); yB = min(a[3], b[3])
        inter = max(0,xB-xA)*max(0,yB-yA)
        areaA = (a[2]-a[0])*(a[3]-a[1])
        areaB = (b[2]-b[0])*(b[3]-b[1])
        denom = areaA+areaB-inter + 1e-6
        return inter/denom if denom>0 else 0.0

    def duration(self, track):
        return max(0.0, track.get('last_ts',0)-track.get('first_ts',0))

    def avg_speed(self, track):
        sp = track.get('speeds')
        if not sp: return 0.0
        return float(sum(sp)/len(sp))
