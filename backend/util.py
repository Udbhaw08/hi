# backend/util.py
import cv2, threading, time

class CameraWrapper:
    def __init__(self, source):
        self.source = source
        self.cap = None
        self.init_camera()
        self.ref_count = 0
        self.last_access = time.time()
        # Threaded capture state
        self._thread = None
        self._stop = False
        self._lock = threading.Lock()
        self.latest_frame = None  # holds most recent frame
        
    def init_camera(self):
        # Try to initialize the camera with different backends if needed
        try:
            if self.cap is not None:
                try:
                    self.cap.release()
                except:
                    pass
                    
            # Try with default backend
            self.cap = cv2.VideoCapture(self.source)
            
            # If that fails, try with DirectShow on Windows
            if not self.cap.isOpened() and isinstance(self.source, int):
                self.cap.release()
                self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
                
            # Try to reduce internal buffering if backend supports it
            if self.cap.isOpened():
                try:
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass
        except Exception as e:
            print(f"Camera initialization error: {str(e)}")
            self.cap = cv2.VideoCapture()

    def _reader(self):
        retry_count = 0
        while not self._stop:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    with self._lock:
                        self.latest_frame = frame
                    retry_count = 0  # Reset retry counter on success
                else:
                    time.sleep(0.1)
                    retry_count += 1
                    # If we fail to read frames multiple times, try to reinitialize
                    if retry_count > 10:
                        print(f"Camera {self.source} failed to read frames, reinitializing...")
                        self.init_camera()
                        retry_count = 0
            else:
                # Camera not opened, try to reinitialize
                time.sleep(0.5)
                self.init_camera()
        # exit

    def _ensure_thread(self):
        if self._thread is None or not self._thread.is_alive():
            self._stop = False
            self._thread = threading.Thread(target=self._reader, daemon=True)
            self._thread.start()

    def acquire(self):
        self.ref_count += 1
        self.last_access = time.time()
        self._ensure_thread()
        return self.cap

    def get_latest_frame(self):
        # Non-blocking latest frame; if not yet available fallback to direct read
        with self._lock:
            frame = self.latest_frame
        if frame is not None:
            return frame
        # fallback (rare during warm-up)
        if self.cap and self.cap.isOpened():
            ret, frame2 = self.cap.read()
            if ret:
                with self._lock:
                    self.latest_frame = frame2
                return frame2
        return None

    def release_ref(self):
        if self.ref_count > 0:
            self.ref_count -= 1
        self.last_access = time.time()

    def needs_close(self, idle_timeout: float):
        return self.ref_count == 0 and (time.time() - self.last_access) > idle_timeout

    def close(self):
        self._stop = True
        try:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=0.5)
        except Exception:
            pass
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass

class CameraManager:
    def __init__(self, idle_timeout=15.0, sweep_interval=5.0):
        self._cams = {}
        self._lock = threading.Lock()
        self.idle_timeout = idle_timeout
        self._sweeper_thread = threading.Thread(target=self._sweeper, daemon=True)
        self._sweeper_thread.start()

    def _sweeper(self):
        while True:
            time.sleep(self.idle_timeout / 3.0)
            with self._lock:
                to_close = [k for k, w in self._cams.items() if w.needs_close(self.idle_timeout)]
                for k in to_close:
                    w = self._cams.pop(k, None)
                    if w:
                        w.close()

    def open(self, source):
        with self._lock:
            wrap = self._cams.get(source)
            if wrap is None or not wrap.cap.isOpened():
                wrap = CameraWrapper(source)
                self._cams[source] = wrap
            return wrap.acquire()

    def get_latest_frame(self, source):
        with self._lock:
            wrap = self._cams.get(source)
        if wrap is None:
            # auto-open if not already
            self.open(source)
            with self._lock:
                wrap = self._cams.get(source)
        if wrap is None:
            return None
        return wrap.get_latest_frame()

    def release(self, source):
        with self._lock:
            wrap = self._cams.get(source)
            if wrap:
                wrap.release_ref()

    def force_release_all(self):
        with self._lock:
            for w in self._cams.values():
                w.close()
            self._cams.clear()

    def status(self):
        with self._lock:
            out = {}
            for k, w in self._cams.items():
                out[str(k)] = {
                    'opened': bool(w.cap and w.cap.isOpened()),
                    'ref_count': w.ref_count,
                    'last_access': w.last_access,
                    'has_frame': w.latest_frame is not None,
                }
            return out

camera_manager = CameraManager()
