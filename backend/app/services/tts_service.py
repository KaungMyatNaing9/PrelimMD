# app/services/tts_service.py
# Text-to-Speech abstraction using ElevenLabs.
# Falls back gracefully to None (no audio) if the API key is missing.
# Routes should treat a None return as "return text response only".
#
# ElevenLabs docs: https://elevenlabs.io/docs/api-reference/text-to-speech

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def synthesize(text: str, voice_id: Optional[str] = None) -> Optional[bytes]:
    """
    Convert text to speech audio bytes using ElevenLabs.

    Returns:
        Raw MP3 audio bytes on success.
        None if the API key is not configured or the call fails.
        Callers should treat None as "use text response only".
    """
    if not settings.elevenlabs_api_key:
        logger.debug("ElevenLabs API key not set — returning text only.")
        return None

    vid = voice_id or settings.elevenlabs_voice_id

    try:
        # Use the ElevenLabs SDK if available
        from elevenlabs import ElevenLabs  # type: ignore

        client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        audio_generator = client.text_to_speech.convert(
            voice_id=vid,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        # SDK returns a generator; collect all chunks into bytes
        return b"".join(audio_generator)

    except ImportError:
        # SDK not installed — fall back to direct HTTP call
        logger.warning("elevenlabs SDK not installed, falling back to httpx.")
        return _synthesize_httpx(text, vid)

    except Exception as exc:
        logger.error("ElevenLabs synthesis failed: %s", exc)
        return None


def _synthesize_httpx(text: str, voice_id: str) -> Optional[bytes]:
    """Direct REST fallback when the ElevenLabs SDK is not installed."""
    try:
        import httpx

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.content

    except Exception as exc:
        logger.error("ElevenLabs HTTP fallback failed: %s", exc)
        return None


def is_available() -> bool:
    """Return True if ElevenLabs is configured and likely to work."""
    return bool(settings.elevenlabs_api_key)
