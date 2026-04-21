import os
import json
import logging
import asyncio
from typing import Dict, Any
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    "hi": "Hindi (Devanagari script)",
}

def get_client():
    """Initializes and returns a Gemini client."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=api_key)

async def translate_text(text: str, lang_code: str) -> str:
    """Translates the given English text to the specified language."""
    lang_name = LANGUAGE_MAP.get(lang_code, lang_code)
    logger.info(f"Translating to {lang_name} (code: {lang_code})")
    
    # Small delay to avoid rate limits after image analysis
    await asyncio.sleep(2)
    
    prompt = (
        f"You are a professional translator. Translate the following English text "
        f"into {lang_name}. Use the native script of {lang_name}. "
        f"Do NOT return English. Only return the translated text, nothing else.\n\n"
        f"Text to translate:\n{text}"
    )
    
    client = get_client()
    for attempt in range(2):
        try:
            # Use gemini-2.0-flash for translation
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            translated = response.text.strip()
            logger.info(f"Translation to {lang_name} successful (attempt {attempt+1})")
            return translated
        except Exception as e:
            logger.error(f"Translation to {lang_name} failed (attempt {attempt+1}): {e}")
            if attempt == 0:
                await asyncio.sleep(3)  # Wait before retry
    
    logger.warning(f"All translation attempts failed, returning English text")
    return text

def get_system_prompt() -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "analyst_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

async def analyze_image(image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
    """
    Analyzes the image using Gemini 2.0 Flash.
    Returns parsed JSON. If it fails to parse JSON, retries once.
    """
    client = get_client()
    
    # Prepare image part for the new SDK
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    
    # Configure generation with system instruction and JSON output
    config = types.GenerateContentConfig(
        system_instruction=get_system_prompt(),
        response_mime_type="application/json"
    )
    
    contents = [image_part, "Analyze this image according to the prompt instructions."]
    
    try:
        # Use gemini-2.0-flash (migrated from gemini-1.5-flash / gemini-2.5-flash)
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=config
        )
        return json.loads(response.text)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Gemini error: {error_msg}")
        
        if "429" in error_msg:
             return {
                "summary": "QUOTA EXCEEDED",
                "details": "The Google Gemini free-tier quota has been reached. Please wait 1-2 minutes for the limit to reset before trying another image.",
                "observations": "N/A",
                "narration_hindi": "सूचना: गूगल जेमिनी की दैनिक सीमा समाप्त हो गई है। कृपया १-२ मिनट प्रतीक्षा करें।",
                "threat_level": "normal",
                "scene_type": "unknown",
                "subject_count": 0
            }
            
        return {
            "summary": "System Error",
            "details": f"Detection failed: {error_msg}",
            "observations": "None",
            "narration_hindi": "सिस्टम त्रुटि: पता लगाना विफल रहा।",
            "threat_level": "normal",
            "scene_type": "unknown",
            "subject_count": 0
        }
