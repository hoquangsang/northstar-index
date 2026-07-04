from __future__ import annotations

from google import genai

from app.config import Settings


def build_gemini_client(settings: Settings) -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required for Gemini operations.")

    return genai.Client(api_key=settings.gemini_api_key)
