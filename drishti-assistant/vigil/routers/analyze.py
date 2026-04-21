from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import logging
import base64

from utils.image_utils import validate_image
from services.gemini_service import analyze_image, translate_text
from services.elevenlabs_service import generate_speech

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/analyze")
async def analyze_endpoint(image: UploadFile = File(...), language: str = Form("en")):
    # 1. Image validation
    image_bytes = await validate_image(image)
    
    # 2. Analyze with Gemini
    analysis_result = await analyze_image(image_bytes, image.content_type)
    
    # 3. Combine text for narration
    threat_level = analysis_result.get("threat_level", "normal")
    
    # Check if we have a direct Hindi narration in the result
    hindi_narration = analysis_result.get("narration_hindi", "")
    
    # Calculate English narrative text for fallback/display
    summary = analysis_result.get("summary", "")
    details = analysis_result.get("details", "")
    observations = analysis_result.get("observations", "")
    narrative_text = f"{summary} {details} {observations}".strip()
    
    if not narrative_text:
        narrative_text = "Analysis yielded no details."
        
    # Determine the final text to use for TTS and return to UI
    tts_text = narrative_text
    if language == "hi":
        tts_text = hindi_narration if hindi_narration else narrative_text
    elif language != "en":
        # Any other language (though we only support hi/en now)
        tts_text = await translate_text(narrative_text, language)
        
    # 4. Generate TTS audio
    audio_bytes = await generate_speech(tts_text, threat_level)
    
    audio_base64 = None
    if audio_bytes:
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        
    # 5. Return JSON payload — use translated text for display too
    return JSONResponse({
        "narration": tts_text,
        "audio_base64": audio_base64,
        "metadata": analysis_result
    })
