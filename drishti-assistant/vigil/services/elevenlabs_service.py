import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def generate_speech(text: str, threat_level: str) -> Optional[bytes]:
    """
    Generates TTS using ElevenLabs.
    If threat_level is "elevated" or "critical", prepends "ALERT. ".
    Returns audio bytes or None if it fails.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB") # Default to Adam
    
    if not api_key:
        logger.error("ELEVENLABS_API_KEY is not set.")
        return None
        
    if threat_level in ["elevated", "critical"]:
        text = f"ALERT. {text}"
        
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.75,
            "similarity_boost": 0.75
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.error(f"ElevenLabs TTS failed: {str(e)}")
        return None
