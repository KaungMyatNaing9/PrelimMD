# app/services/voice_service.py
# Voice processing — speech-to-text via Deepgram.
# Owner: Voice teammate
#
# TODO: Voice - implement synthesize() when TTS is needed

import asyncio
import contextlib
import json
import re
from typing import Any

from deepgram import AsyncDeepgramClient, DeepgramClient
from deepgram.listen.v1.types.listen_v1results import ListenV1Results
from fastapi import WebSocket
from openai import OpenAI

from app.config import settings
from app.models.schemas import IntakeCallSession, TranscribeResponse
from app.services import store

_RELATED_BATCHES = {
    "insurance_provider": {"insurance_id"},
    "insurance_id": {"insurance_provider"},
    "emergency_contact_name": {"emergency_contact_phone", "emergency_contact_relation"},
    "emergency_contact_phone": {"emergency_contact_name"},
    "emergency_contact_relation": {"emergency_contact_name"},
    "phone": {"email"},
    "email": {"phone"},
}

_BATCH_PROMPTS = {
    frozenset({"insurance_provider", "insurance_id"}): (
        "What insurance are you using, and do you have your member ID handy?",
        "You can say both the insurance company name and the member ID in one answer.",
    ),
    frozenset({"emergency_contact_name", "emergency_contact_phone"}): (
        "Who should we contact in an emergency, and what is the best number for them?",
        "You can say the person's name and phone number together.",
    ),
    frozenset({"emergency_contact_name", "emergency_contact_relation"}): (
        "Who is your emergency contact, and how are they related to you?",
        "You can say the person's name and relationship together.",
    ),
    frozenset({"phone", "email"}): (
        "What are the best phone number and email address for your records?",
        "You can give both your phone number and email in one answer.",
    ),
}


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
    stream_state: dict[str, Any] = {
        "pace": "guided",
        "visit_id": None,
        "field_ids": [],
        "current_field_id": None,
        "current_question": None,
        "help_text": None,
        "remaining_fields": [],
    }
    dg_socket = None
    dg_context = None
    transcript_task: asyncio.Task[None] | None = None
    client = AsyncDeepgramClient(api_key=settings.deepgram_api_key) if settings.deepgram_api_key else None

    async def ensure_dg_socket():
        nonlocal dg_socket, dg_context, transcript_task
        if dg_socket is not None or client is None:
            return dg_socket

        dg_context = client.listen.v1.connect(
            model="nova-3",
            endpointing=300,
            smart_format="true",
            interim_results="true",
        )
        dg_socket = await dg_context.__aenter__()
        transcript_task = asyncio.create_task(handle_transcripts(dg_socket))
        return dg_socket

    async def close_dg_socket() -> None:
        nonlocal dg_socket, dg_context, transcript_task
        if transcript_task is not None:
            transcript_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await transcript_task
            transcript_task = None
        if dg_context is not None:
            with contextlib.suppress(Exception):
                await dg_context.__aexit__(None, None, None)
            dg_context = None
        dg_socket = None

    async def handle_browser_messages() -> None:
        """Read mixed browser messages: raw audio bytes or JSON assistant events."""
        nonlocal dg_socket
        while True:
            message = await browser_ws.receive()
            if message["type"] == "websocket.disconnect":
                break

            chunk = message.get("bytes")
            if chunk is not None:
                active_socket = dg_socket
                if active_socket is None and client is not None:
                    active_socket = await ensure_dg_socket()
                    dg_socket = active_socket
                if active_socket is not None:
                    try:
                        await active_socket.send_media(chunk)
                    except Exception:
                        await close_dg_socket()
                continue

            text = message.get("text")
            if not text:
                continue

            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue

            if payload.get("type") == "ping":
                await browser_ws.send_json({"type": "pong"})
                continue

            if payload.get("type") == "context":
                stream_state.update({
                    "pace": str(payload.get("pace") or "guided"),
                    "visit_id": payload.get("visit_id"),
                    "current_field_id": payload.get("current_field_id"),
                    "remaining_fields": payload.get("remaining_fields") or [],
                })
                plan = _choose_question_plan(stream_state)
                stream_state.update(plan)
                await browser_ws.send_json({"type": "plan", **plan})
                continue

            if payload.get("type") != "utterance":
                continue

            transcript = str(payload.get("transcript") or "").strip()
            if not transcript:
                continue

            assistant_reply = await _call_llm(transcript, {**stream_state, **payload})
            _persist_assistant_exchange(
                visit_id=stream_state.get("visit_id"),
                transcript=transcript,
                reply=assistant_reply.get("reply", ""),
                field_ids=assistant_reply.get("consumed_field_ids") or stream_state.get("field_ids") or [],
                extracted_answers=assistant_reply.get("extracted_answers") or {},
            )
            await browser_ws.send_json({"type": "assistant", "transcript": transcript, **assistant_reply})

    async def handle_transcripts(dg_socket) -> None:
        """Read Deepgram events and send structured JSON to browser."""
        nonlocal transcript_task
        try:
            async for event in dg_socket:
                if not isinstance(event, ListenV1Results):
                    continue

                transcript = event.channel.alternatives[0].transcript
                if not transcript:
                    continue

                confidence = event.channel.alternatives[0].confidence

                if event.speech_final:
                    assistant_reply = await _call_llm(transcript, stream_state)
                    _persist_assistant_exchange(
                        visit_id=stream_state.get("visit_id"),
                        transcript=transcript,
                        reply=assistant_reply.get("reply", ""),
                        field_ids=assistant_reply.get("consumed_field_ids") or stream_state.get("field_ids") or [],
                        extracted_answers=assistant_reply.get("extracted_answers") or {},
                    )
                    await browser_ws.send_json({
                        "type": "assistant",
                        "transcript": transcript,
                        "confidence": confidence,
                        **assistant_reply,
                    })
                elif event.is_final:
                    await browser_ws.send_json({
                        "type": "partial",
                        "transcript": transcript,
                        "confidence": confidence,
                    })
        except asyncio.CancelledError:
            raise
        except Exception:
            if browser_ws.client_state.name == "CONNECTED":
                with contextlib.suppress(Exception):
                    await browser_ws.send_json({
                        "type": "error",
                        "message": "Live listening paused. Start speaking again.",
                    })
        finally:
            transcript_task = None

    if not settings.deepgram_api_key:
        await handle_browser_messages()
        return

    try:
        await handle_browser_messages()
    finally:
        await close_dg_socket()


def _local_assistant_response(transcript: str, payload: dict[str, Any]) -> dict[str, Any]:
    pace = str(payload.get("pace") or "guided")
    help_text = str(payload.get("help_text") or "").strip()
    question = str(payload.get("question") or "").strip()
    lowered = transcript.lower()

    asks_for_help = any(phrase in lowered for phrase in (
        "what does that mean",
        "what do you mean",
        "can you explain",
        "i don't know",
        "not sure",
        "help me",
    ))
    wants_repeat = any(phrase in lowered for phrase in ("repeat", "say it again", "what was the question"))
    if asks_for_help and help_text:
        return {
            "reply": f"No problem. {help_text}",
            "mode": pace,
            "should_repeat": False,
            "speed_hint": "slow",
            "extracted_answers": {},
            "consumed_field_ids": list(payload.get("field_ids") or []),
        }
    if wants_repeat and question:
        return {
            "reply": question,
            "mode": pace,
            "should_repeat": True,
            "speed_hint": "slow",
            "extracted_answers": {},
            "consumed_field_ids": list(payload.get("field_ids") or []),
        }

    if pace == "quick":
        return {
            "reply": "Saved. Moving on.",
            "mode": pace,
            "should_repeat": False,
            "speed_hint": "fast",
            "extracted_answers": {},
            "consumed_field_ids": list(payload.get("field_ids") or []),
        }

    return {
        "reply": "Thanks. I saved that answer for your form.",
        "mode": pace,
        "should_repeat": False,
        "speed_hint": "steady",
        "extracted_answers": {},
        "consumed_field_ids": list(payload.get("field_ids") or []),
    }


async def _call_llm(transcript: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Generate a concise assistant reply for the browser voice guide.
    Falls back to deterministic behavior if OpenAI is not configured.
    """
    extracted_answers = await _extract_answers(transcript, payload)
    local = _local_assistant_response(transcript, payload)
    local["extracted_answers"] = extracted_answers
    local["consumed_field_ids"] = list(extracted_answers.keys()) or list(payload.get("field_ids") or [])
    if not settings.openai_api_key:
        return local

    current_label = str(payload.get("field_label") or "")
    question = str(payload.get("question") or "")
    help_text = str(payload.get("help_text") or "")
    pace = str(payload.get("pace") or "guided")
    remaining_fields = payload.get("remaining_fields") or []
    remaining_display = ", ".join(str(field.get("label")) for field in remaining_fields[:5])

    system = """
You are a concise medical intake voice assistant for a patient self check-in kiosk.
Reply in a warm, efficient way.

Rules:
- Keep replies very short.
- Do not lecture.
- If the patient sounds confused, explain the current question briefly using the help text.
- If the patient asks to repeat, repeat only the current question.
- In quick mode, prefer ultra-short acknowledgements.
- Return only JSON with keys: reply, should_repeat, speed_hint.
speed_hint must be one of: fast, steady, slow.
""".strip()

    user = json.dumps(
        {
            "transcript": transcript,
            "current_field_label": current_label,
            "current_question": question,
            "help_text": help_text,
            "pace": pace,
            "remaining_labels": remaining_display,
            "field_ids": payload.get("field_ids") or [],
        }
    )

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
        reply = str(parsed.get("reply") or "").strip()
        speed_hint = str(parsed.get("speed_hint") or "steady").strip().lower()
        if speed_hint not in {"fast", "steady", "slow"}:
            speed_hint = "steady"
        return {
            "reply": reply or _local_assistant_response(transcript, payload)["reply"],
            "mode": pace,
            "should_repeat": bool(parsed.get("should_repeat")),
            "speed_hint": speed_hint,
            "extracted_answers": extracted_answers,
            "consumed_field_ids": list(extracted_answers.keys()) or list(payload.get("field_ids") or []),
        }
    except Exception:
        return local


def _choose_question_plan(stream_state: dict[str, Any]) -> dict[str, Any]:
    remaining = stream_state.get("remaining_fields") or []
    pace = str(stream_state.get("pace") or "guided")
    current_field_id = stream_state.get("current_field_id")

    if not remaining:
        return {"field_ids": [], "prompt": "", "help_text": "", "speed_hint": "steady"}

    current = next((field for field in remaining if field.get("field_id") == current_field_id), remaining[0])
    batch = [current]
    if pace == "quick":
        related_ids = _RELATED_BATCHES.get(str(current.get("field_id")), set())
        for candidate in remaining:
            if candidate.get("field_id") == current.get("field_id"):
                continue
            if candidate.get("field_id") in related_ids:
                batch.append(candidate)
                break

    field_ids = [str(field.get("field_id")) for field in batch]
    prompt, help_text = _prompt_for_batch(batch)
    speed_hint = "fast" if pace == "quick" else "steady"
    return {
        "field_ids": field_ids,
        "prompt": prompt,
        "help_text": help_text,
        "speed_hint": speed_hint,
    }


def _prompt_for_batch(fields: list[dict[str, Any]]) -> tuple[str, str]:
    field_ids = frozenset(str(field.get("field_id")) for field in fields)
    if field_ids in _BATCH_PROMPTS:
        return _BATCH_PROMPTS[field_ids]

    primary = fields[0]
    label = str(primary.get("label") or primary.get("field_id") or "this field")
    prompt = label if label.endswith("?") else f"{label}?"
    help_text = f"You can answer in your own words and I will save it for {label.lower()}."
    return prompt, help_text


async def _extract_answers(transcript: str, payload: dict[str, Any]) -> dict[str, str]:
    remaining = payload.get("remaining_fields") or []
    field_ids = [str(field_id) for field_id in payload.get("field_ids") or []]
    descriptors = [
        next((field for field in remaining if str(field.get("field_id")) == field_id), {"field_id": field_id, "label": field_id, "type": "string"})
        for field_id in field_ids
    ]
    if not descriptors:
        return {}

    if not settings.openai_api_key:
        return {field_ids[0]: transcript} if field_ids else {}

    system = """
Extract patient answers for one or two intake form fields from a spoken utterance.
Return only JSON as an object mapping field_id to extracted value.
- If a field was not answered clearly, omit it.
- Keep values short and normalized.
- For yes/no fields, return "yes" or "no".
""".strip()
    user = json.dumps({"transcript": transcript, "fields": descriptors})
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {
                str(key): str(value).strip()
                for key, value in parsed.items()
                if value not in (None, "", [], {})
            }
    except Exception:
        pass
    return {field_ids[0]: transcript} if field_ids else {}


def _persist_assistant_exchange(
    visit_id: str | None,
    transcript: str,
    reply: str,
    field_ids: list[str],
    extracted_answers: dict[str, str],
) -> None:
    if not visit_id:
        return
    visit = store.get_visit(visit_id)
    if not visit:
        return

    session_id = f"kiosk-{visit_id}"
    session = store.get_session(session_id)
    if not session:
        session = IntakeCallSession(
            session_id=session_id,
            session_type="intake",
            visit_id=visit_id,
            patient_id=visit.patient_id,
            status="in_progress",
            conversation=[],
            collected_answers={},
            flags=[],
            created_at=store.now_iso(),
        )
        store.save_session(session)

    session = store.get_session(session_id) or session
    patient_turn = {
        "turn_id": store.new_id("t-"),
        "role": "patient",
        "content": transcript,
        "timestamp": store.now_iso(),
        "field_ids_targeted": field_ids,
    }
    ai_turn = {
        "turn_id": store.new_id("t-"),
        "role": "ai",
        "content": reply,
        "timestamp": store.now_iso(),
        "field_ids_targeted": field_ids,
    }
    merged_answers = {**session.collected_answers, **extracted_answers}
    store.update_session(
        session_id,
        {
            "conversation": [*session.conversation, patient_turn, ai_turn],
            "collected_answers": merged_answers,
        },
    )


def synthesize(text: str) -> bytes:
    """Convert text to speech audio bytes."""
    # TODO: Voice - implement with chosen TTS provider
    raise NotImplementedError
