# config.py
import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DETECTED_FOLDER = os.path.join(BASE_DIR, "detected_frames")   # where your detection pipeline writes frames
INDEX_PATH = os.path.join(BASE_DIR, "index.jsonl")            # where processed records are saved

# Models
IMAGE_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CAPTION_MODEL = "Salesforce/blip-image-captioning-base"
DEVICE = "cpu"    # change to "cuda" if torch GPU available

# LLM config - using transformers by default (more accessible)
USE_LLAMA_CPP = False
LLAMA_CPP_MODEL_PATH = ""  # Not using llama-cpp by default
TRANSFORMERS_MODEL = "facebook/opt-350m"  # Better model for reasoning than gpt2
TOP_K = 5  # number of frames to retrieve for a query

# Analysis settings
ANALYSIS_TYPES = ["people", "objects", "activities", "safety", "general"]
