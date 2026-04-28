# app/services/voice_service.py
# Voice processing — speech-to-text via Deepgram.
# Owner: Voice teammate
#
# TODO: Voice - implement synthesize() when TTS is needed

import asyncio

from deepgram import AsyncDeepgramClient, DeepgramClient
from deepgram.listen.v1.types.listen_v1results import ListenV1Results
from fastapi import WebSocket

from app.config import settings
from app.models.schemas import TranscribeResponse


# ── Pre-recorded (file upload) ────────────────────────────────────────────────

def transcribe(audio_bytes: bytes) -> TranscribeResponse:
    """
    Send raw audio bytes to Deepgram and return a structured transcript.
    Field paths verified against deepgram-sdk v6.1.1 source.
    """
    client = DeepgramClient(api_key=settings.deepgram_api_key)

    response = client.listen.v1.media.transcribe_file(
        request=audio_bytes,
        model="nova-3",
        smart_format=True,
        detect_language=True,
    )

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


# ── Live streaming ────────────────────────────────────────────────────────────

async def stream_session(browser_ws: WebSocket) -> None:
    """
    Bridge a browser WebSocket to Deepgram's live streaming API.

    Audio format expected from browser: linear16 PCM, 16000 Hz mono.
    Sends JSON events back to the browser:
      - type "partial"  → interim result while person is still speaking
      - type "final"    → speech_final fired (pause detected), transcript sent to LLM
    """
    client = AsyncDeepgramClient(api_key=settings.deepgram_api_key)

    async with client.listen.v1.connect(
        model="nova-3",
        endpointing=300,           # fire speech_final after 300 ms of silence
        smart_format="true",       # SDK bug: booleans must be strings for WS params
        interim_results="true",    # send partials so browser can show live text
    ) as dg_socket:

        async def forward_audio() -> None:
            """Read audio chunks from browser and forward to Deepgram."""
            async for chunk in browser_ws.iter_bytes():
                await dg_socket.send_media(chunk)

        async def handle_transcripts() -> None:
            """Read Deepgram events and send structured JSON to browser."""
            async for event in dg_socket:
                if not isinstance(event, ListenV1Results):
                    continue

                transcript = event.channel.alternatives[0].transcript
                if not transcript:
                    continue

                confidence = event.channel.alternatives[0].confidence

                if event.speech_final:
                    # Pause detected — this is one complete utterance
                    llm_response = await _call_llm(transcript)
                    await browser_ws.send_json({
                        "type": "final",
                        "transcript": transcript,
                        "confidence": confidence,
                        "llm_response": llm_response,
                    })
                elif event.is_final:
                    # Deepgram committed this chunk but speech isn't done yet
                    await browser_ws.send_json({
                        "type": "partial",
                        "transcript": transcript,
                        "confidence": confidence,
                    })

        await asyncio.gather(forward_audio(), handle_transcripts())


async def _call_llm(transcript: str) -> str:
    """
    Send a final transcript to the LLM interview engine.
    TODO: AI teammate — replace this placeholder with real LLM call.
    """
    return f"[LLM placeholder] Received utterance: {transcript}"


def synthesize(text: str) -> bytes:
    """Convert text to speech audio bytes."""
    # TODO: Voice - implement with chosen TTS provider
    raise NotImplementedError
