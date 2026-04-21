# VIGIL

**Visual Intelligence & Guided Insight Layer**

VIGIL is a multimodal AI system that takes an image as input, understands what's in it using Google Gemini Vision, generates a structured intelligent narration, and speaks it aloud using ElevenLabs TTS.

## Setup Instructions

1. Clone or download the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add your API keys:
   - **Gemini API Key**: Get it from Google AI Studio.
   - **ElevenLabs API Key**: Get it from the ElevenLabs dashboard.
4. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

## Tech Stack
- Frontend: HTML/CSS/JS (Vanilla)
- Backend: FastAPI
- AI Vision: Google Gemini (1.5-flash)
- AI Voice: ElevenLabs TTS
