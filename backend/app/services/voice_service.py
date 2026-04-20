# app/services/voice_service.py
# Voice processing — speech-to-text via Deepgram.
# Owner: Voice teammate
#
# TODO: Voice - implement synthesize() when TTS is needed

from deepgram import DeepgramClient

from app.config import settings
from app.models.schemas import TranscribeResponse


def transcribe(audio_bytes: bytes) -> TranscribeResponse:
    """
    Send raw audio bytes to Deepgram and return a structured transcript.

    Uses nova-3 with smart_format and detect_language.
    Field paths verified against deepgram-sdk v6.1.1 source.
    """
    client = DeepgramClient(api_key=settings.deepgram_api_key)

    response = client.listen.v1.media.transcribe_file(
        request=audio_bytes,
        model="nova-3",
        smart_format=True,      # punctuation, casing, numerals
        detect_language=True,   # populate detected_language on each channel
    )

    # Extract fields from the verified response structure
    alt = response.results.channels[0].alternatives[0]
    channel = response.results.channels[0]

    return TranscribeResponse(
        success=True,
        transcript=alt.transcript or "",
        confidence=alt.confidence,
        language=channel.detected_language,
        duration=response.metadata.duration,
        raw=response.model_dump(),
    )


def synthesize(text: str) -> bytes:
    """Convert text to speech audio bytes."""
    # TODO: Voice - implement with chosen TTS provider
    raise NotImplementedError
