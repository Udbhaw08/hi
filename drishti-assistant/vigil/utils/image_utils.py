import base64
from fastapi import UploadFile, HTTPException
from PIL import Image
import io

MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
SUPPORTED_FORMATS = ["image/jpeg", "image/png"]

async def validate_image(file: UploadFile) -> bytes:
    """
    Validates the uploaded image for type and size constraints.
    Returns the raw bytes if valid.
    """
    if file.content_type not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG supported")
    
    # Read file content
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large")
        
    # Optional: Verify it's actually an image using Pillow
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid image file")
        
    return content

def encode_image_base64(image_bytes: bytes) -> str:
    """
    Encodes image bytes to base64 string.
    """
    return base64.b64encode(image_bytes).decode("utf-8")
