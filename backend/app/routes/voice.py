# app/routes/voice.py
# HTTP routes for voice input/output processing.
# Owner: Voice teammate
#
# TODO: Voice - POST /synthesize → accept text, return audio stream (TTS)

from fastapi import APIRouter, HTTPException, UploadFile

from app.config import settings
from app.models.schemas import TranscribeResponse
from app.services import voice_service

router = APIRouter()

# Audio/video MIME types accepted for transcription
ALLOWED_MIME_TYPES = {
    "audio/wav",
    "audio/mpeg",       # mp3
    "audio/mp4",        # m4a
    "audio/webm",
    "video/webm",
    "video/mp4",
    # browsers sometimes send these variants
    "audio/x-wav",
    "audio/x-m4a",
}


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile):
    """
    Accept an audio/video file upload and return a transcript.

    Supports: wav, mp3, m4a, webm, mp4
    """
    # Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Allowed: wav, mp3, m4a, webm, mp4.",
        )

    audio_bytes = await file.read()

    # Validate file size
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_file_size_mb} MB.",
        )

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        return voice_service.transcribe(audio_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Deepgram transcription failed: {exc}",
        )


@router.post("/synthesize")
def synthesize_speech():
    # TODO: Voice - call voice_service.synthesize() with text payload
    return {"message": "placeholder — speech synthesis not yet implemented"}
