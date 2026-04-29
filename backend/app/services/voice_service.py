import asyncio
import json
from io import BytesIO

from elevenlabs.client import AsyncElevenLabs, ElevenLabs
from fastapi import WebSocket

from app.config import settings
from app.models.schemas import TranscribeResponse

_MIN_TRANSCRIBE_BYTES = 4_000


def _sync_client() -> ElevenLabs:
    return ElevenLabs(api_key=settings.elevenlabs_api_key)


def _async_client() -> AsyncElevenLabs:
    return AsyncElevenLabs(api_key=settings.elevenlabs_api_key)


# ── Pre-recorded file upload ──────────────────────────────────────────────────

def transcribe(audio_bytes: bytes) -> TranscribeResponse:
    client = _sync_client()
    audio_io = BytesIO(audio_bytes)
    audio_io.name = "audio.webm"
    result = client.speech_to_text.convert(file=audio_io, model_id="scribe_v1")
    return TranscribeResponse(
        success=True,
        transcript=result.text or "",
        confidence=None,
        language=getattr(result, "language_code", None),
        duration=None,
        raw={},
    )


# ── Live streaming ────────────────────────────────────────────────────────────

async def stream_session(browser_ws: WebSocket, session_id: str | None = None) -> None:
    """
    Collect mic audio from the browser, transcribe with ElevenLabs Scribe,
    and return the result.

    Protocol (browser → backend):
      - Binary frames: raw audio chunks from MediaRecorder
      - Text frame {"type": "stop"}: patient finished speaking — trigger transcription

    Protocol (backend → browser):
      {"type": "connected"}              — WebSocket is live and ready
      {"type": "partial", "transcript": "Listening…"}  — audio is being received
      {"type": "transcribing"}           — stop received, transcribing now
      {"type": "final", "transcript": "...", "llm_response": "..."}  — done
      {"type": "error", "message": "..."}  — something failed
    """
    audio_buffer = bytearray()

    # Let the frontend know the connection is live
    await browser_ws.send_json({"type": "connected"})

    # ── Collect audio until the patient signals they're done ──────────────────
    heartbeat_counter = 0
    while True:
        try:
            raw = await browser_ws.receive()
        except Exception:
            # WebSocket disconnected without sending stop — still try to transcribe
            break

        msg_type = raw.get("type")

        if msg_type == "websocket.disconnect":
            break

        if msg_type == "websocket.receive":
            audio_chunk = raw.get("bytes")
            text_frame = raw.get("text")

            if audio_chunk:
                audio_buffer.extend(audio_chunk)
                # Send a heartbeat every ~40 chunks so the frontend knows we're alive
                heartbeat_counter += 1
                if heartbeat_counter % 40 == 0:
                    try:
                        await browser_ws.send_json({"type": "partial", "transcript": "Listening…"})
                    except Exception:
                        break

            elif text_frame:
                try:
                    msg = json.loads(text_frame)
                    if msg.get("type") == "stop":
                        # Patient stopped speaking — acknowledge and break to transcribe
                        await browser_ws.send_json({"type": "transcribing"})
                        break
                except (json.JSONDecodeError, Exception):
                    pass

    # ── Transcribe everything we collected ────────────────────────────────────
    if len(audio_buffer) < _MIN_TRANSCRIBE_BYTES:
        try:
            await browser_ws.send_json({"type": "error", "message": "Audio too short — please speak for a moment."})
        except Exception:
            pass
        return

    try:
        client = _async_client()
        audio_io = BytesIO(bytes(audio_buffer))
        audio_io.name = "audio.webm"
        result = await client.speech_to_text.convert(file=audio_io, model_id="scribe_v1")
        final_text = (result.text or "").strip()
    except Exception as exc:
        try:
            await browser_ws.send_json({"type": "error", "message": f"Transcription failed: {exc}"})
        except Exception:
            pass
        return

    if not final_text:
        try:
            await browser_ws.send_json({"type": "error", "message": "Could not make out what was said. Please try again."})
        except Exception:
            pass
        return

    llm_response = await _call_llm(final_text, session_id)

    try:
        await browser_ws.send_json({
            "type": "final",
            "transcript": final_text,
            "llm_response": llm_response,
        })
    except Exception:
        pass


# ── Text-to-speech ────────────────────────────────────────────────────────────

async def synthesize(text: str, voice_id: str | None = None) -> bytes:
    client = _async_client()
    vid = voice_id or settings.elevenlabs_voice_id
    chunks: list[bytes] = []
    async for chunk in client.text_to_speech.convert(
        voice_id=vid,
        text=text,
        model_id="eleven_turbo_v2_5",
        output_format="mp3_44100_128",
    ):
        chunks.append(chunk)
    return b"".join(chunks)


# ── LLM bridge ────────────────────────────────────────────────────────────────

async def _call_llm(transcript: str, session_id: str | None = None) -> str:
    if not session_id:
        return ""
    try:
        from app.services.ai_engine import process_response
        result = await process_response(session_id, transcript)
        return result.get("message", "")
    except Exception:
        return ""
