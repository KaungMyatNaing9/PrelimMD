from fastapi import APIRouter, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel
from starlette.websockets import WebSocketState

from app.config import settings
from app.models.schemas import TranscribeResponse
from app.services import voice_service

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "audio/wav", "audio/mpeg", "audio/mp4", "audio/webm",
    "video/webm", "video/mp4", "audio/x-wav", "audio/x-m4a",
}


# ── Pre-recorded file upload ──────────────────────────────────────────────────

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'.",
        )
    audio_bytes = await file.read()
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_file_size_mb} MB limit.")
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        return voice_service.transcribe(audio_bytes)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}")


# ── Live streaming WebSocket ──────────────────────────────────────────────────

@router.websocket("/stream")
async def stream_audio(websocket: WebSocket):
    """
    Live speech-to-text via WebSocket (ElevenLabs Scribe).
    Optional query param: ?session_id=<id> — when provided, the final transcript
    is fed into the Maya AI engine and her response comes back in llm_response.

    Events sent to the browser:
      {"type": "partial", "transcript": "..."}
      {"type": "final",   "transcript": "...", "llm_response": "..."}
      {"type": "error",   "message": "..."}
    """
    session_id: str | None = websocket.query_params.get("session_id")
    await websocket.accept()
    try:
        await voice_service.stream_session(websocket, session_id=session_id)
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


# ── Text-to-speech ────────────────────────────────────────────────────────────

class SynthesizeRequest(BaseModel):
    text: str
    voice_id: str | None = None


@router.post("/synthesize")
async def synthesize_speech(body: SynthesizeRequest):
    """Convert text to speech using ElevenLabs. Returns MP3 audio bytes."""
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    try:
        audio_bytes = await voice_service.synthesize(body.text, voice_id=body.voice_id)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Speech synthesis failed: {exc}")
