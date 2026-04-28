# app/routes/voice.py
# HTTP and WebSocket routes for voice input/output processing.
# Owner: Voice teammate
#
# ── Frontend integration guide for /voice/stream ─────────────────────────────
#
# 1. Open a WebSocket:
#      const ws = new WebSocket("ws://localhost:8000/voice/stream")
#
# 2. Capture mic audio with MediaRecorder and stream chunks:
#      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
#      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" })
#      recorder.ondataavailable = (e) => e.data.arrayBuffer().then(buf => ws.send(buf))
#      recorder.start(250)  // send a chunk every 250ms
#
# 3. Listen for JSON messages from the server:
#
#      Partial (person still speaking):
#        { "type": "partial", "transcript": "...", "confidence": 0.95 }
#
#      Final (pause detected — full utterance + LLM response):
#        { "type": "final", "transcript": "...", "confidence": 0.99, "llm_response": "..." }
#
#      Error:
#        { "type": "error", "message": "..." }
#
# See backend/test_stream.html for a complete working browser example.
#
# TODO: Voice - POST /synthesize → accept text, return audio stream (TTS)

from fastapi import APIRouter, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import settings
from app.models.schemas import TranscribeResponse
from app.services import voice_service

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "audio/wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/webm",
    "video/webm",
    "video/mp4",
    "audio/x-wav",
    "audio/x-m4a",
}


# ── Pre-recorded file upload ──────────────────────────────────────────────────

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile):
    """Accept an audio/video file upload and return a transcript."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Allowed: wav, mp3, m4a, webm, mp4.",
        )

    audio_bytes = await file.read()

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
        raise HTTPException(status_code=502, detail=f"Deepgram transcription failed: {exc}")


# ── Live streaming ────────────────────────────────────────────────────────────

@router.websocket("/stream")
async def stream_audio(websocket: WebSocket):
    """
    Live transcription via WebSocket.

    Browser sends raw linear16 PCM audio chunks (16000 Hz mono).
    Backend streams to Deepgram and returns JSON events:

      {"type": "partial", "transcript": "...", "confidence": 0.9}
      {"type": "final",   "transcript": "...", "confidence": 0.99, "llm_response": "..."}

    "final" fires on every pause (Deepgram endpointing at 300 ms silence).
    The llm_response field is currently a placeholder for the AI teammate.
    """
    await websocket.accept()
    try:
        await voice_service.stream_session(websocket)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
        if (
            websocket.application_state != WebSocketState.DISCONNECTED
            and websocket.client_state != WebSocketState.DISCONNECTED
        ):
            try:
                await websocket.close(code=1011, reason=str(exc))
            except RuntimeError:
                pass


@router.post("/synthesize")
def synthesize_speech():
    # TODO: Voice - call voice_service.synthesize() with text payload
    return {"message": "placeholder — speech synthesis not yet implemented"}
