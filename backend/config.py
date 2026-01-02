# backend/config.py
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "nsg_security")

# Camera sources mapping; can be device indices or RTSP/HTTP URLs
# Try multiple camera options to ensure at least one works
CAMERA_SOURCES = {
    0: os.getenv("CAM0_SOURCE", "0"),  # Can be int index or string URL
    1: os.getenv("CAM1_SOURCE", "1"),  # Can be int index or string URL
}

# Convert numeric strings to integers for device indices
for key in CAMERA_SOURCES:
    if isinstance(CAMERA_SOURCES[key], str) and CAMERA_SOURCES[key].isdigit():
        CAMERA_SOURCES[key] = int(CAMERA_SOURCES[key])

# Matching threshold override (env optional)
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", 0.45))

# Run full face detection every N frames (frames in between reuse last boxes)
DETECTION_SKIP = int(os.getenv("DETECTION_SKIP", 1))  # 1 = detect every frame
