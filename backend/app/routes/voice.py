import re
from pathlib import Path
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import settings
from app.models.schemas import (
    FollowUpResponse,
    FormSchema,
    IntakeCallSession,
    MissingField,
    TranscribeResponse,
    VoiceCallSession,
    VoiceOutboundCallRequest,
    VoiceOutboundCallResponse,
)
from app.services import ai_engine, interview_engine, store, tts_service, voice_service

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "audio/wav", "audio/mpeg", "audio/mp4", "audio/webm",
    "video/webm", "video/mp4", "audio/x-wav", "audio/x-m4a",
}
PHONE_BLOCKLIST = {"ssn", "social_security", "patient_signature", "signature", "consent_signature", "consent_date"}
DECLINE_PATTERNS = ("i don't want to answer", "do not want to answer", "skip", "not answering", "prefer not to", "decline")
UNCLEAR_PATTERNS = ("maybe", "i don't know", "dont know", "kind of", "not sure", "unsure", "possibly")
WRONG_PATIENT_PATTERNS = ("wrong person", "wrong number", "not the patient", "not who you are looking for", "you have the wrong")
MEDICAL_ADVICE_PATTERNS = ("what should i do", "should i", "do i need to", "is this normal", "can i take", "should i stop", "should i start")
GLOBAL_CONCERN_KEYWORDS = (
    "getting worse", "worse", "severe pain", "trouble breathing", "bad side effects",
    "stopped taking medication", "stopped my medication", "chest pain", "shortness of breath",
)
TWILIO_SAY_VOICE = "alice"
STATIC_TTS_DIR = Path(__file__).resolve().parents[2] / "static" / "tts"


# ════════════════════════════════════════════════════════════════════════════
# STT — Pre-recorded file upload
# ════════════════════════════════════════════════════════════════════════════

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: wav, mp3, m4a, webm, mp4.",
        )

    audio_bytes = await file.read()
    max_bytes = settings.max_file_size_mb * 1024 * 1024

    if len(audio_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Max {settings.max_file_size_mb} MB.")
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        return voice_service.transcribe(audio_bytes)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Deepgram transcription failed: {exc}")


# ════════════════════════════════════════════════════════════════════════════
# STT — Live WebSocket streaming
# ════════════════════════════════════════════════════════════════════════════

@router.websocket("/stream")
async def stream_audio(websocket: WebSocket):
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


# ════════════════════════════════════════════════════════════════════════════
# TTS — Text to Speech
# ════════════════════════════════════════════════════════════════════════════

@router.post("/synthesize")
async def synthesize_speech(request: Request, text: str | None = None):
    payload = await _incoming_params(request)
    prompt = text or payload.get("text")
    if not prompt:
        raise HTTPException(status_code=422, detail="text is required.")

    audio = tts_service.synthesize(prompt)
    if audio:
        return Response(content=audio, media_type="audio/mpeg")
    return {"text": prompt, "audio_available": False, "message": "ElevenLabs not configured — use text fallback."}


# ════════════════════════════════════════════════════════════════════════════
# Twilio call flows
# ════════════════════════════════════════════════════════════════════════════

@router.api_route("/intake/start", methods=["GET", "POST"])
async def voice_intake_start(
    request: Request,
    session_id: str | None = Query(default=None),
    visit_id: str | None = Query(default=None),
    call_sid: str | None = Query(default=None),
):
    session = _resolve_intake_session(session_id=session_id, visit_id=visit_id)
    twilio = await _incoming_params(request)
    resolved_call_sid = twilio.get("CallSid") or call_sid or f"manual-{store.new_id('call-')}"
    call_session, created = _load_or_create_call_session(
        call_sid=resolved_call_sid,
        session=session,
        mode="intake",
        from_phone=twilio.get("From"),
        to_phone=twilio.get("To"),
    )

    prompt = "Hello, this is PrelimMD calling on behalf of your care team. Before we begin, please say your full name."
    if created:
        _append_ai_turn(session.session_id, prompt, ["full_name"])

    return _gather_response(
        prompt,
        action_path="/voice/intake/answer",
        query={"call_sid": resolved_call_sid},
    )


@router.post("/intake/answer")
async def voice_intake_answer(request: Request, call_sid: str | None = Query(default=None)):
    return await _handle_answer(request=request, mode="intake", explicit_call_sid=call_sid)


@router.api_route("/followup/start", methods=["GET", "POST"])
async def voice_followup_start(
    request: Request,
    session_id: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    followup_id: str | None = Query(default=None),
    call_sid: str | None = Query(default=None),
):
    session = _resolve_followup_session(session_id=session_id, task_id=task_id or followup_id)
    twilio = await _incoming_params(request)
    resolved_call_sid = twilio.get("CallSid") or call_sid or f"manual-{store.new_id('call-')}"
    call_session, created = _load_or_create_call_session(
        call_sid=resolved_call_sid,
        session=session,
        mode="followup",
        from_phone=twilio.get("From"),
        to_phone=twilio.get("To"),
    )

    prompt = "Hello, this is PrelimMD calling on behalf of your care team. Before we begin, please say your full name."
    if created:
        _append_ai_turn(session.session_id, prompt, ["full_name"])

    return _gather_response(
        prompt,
        action_path="/voice/followup/answer",
        query={"call_sid": resolved_call_sid},
    )


@router.post("/followup/answer")
async def voice_followup_answer(request: Request, call_sid: str | None = Query(default=None)):
    return await _handle_answer(request=request, mode="followup", explicit_call_sid=call_sid)


@router.post("/call/start", response_model=VoiceOutboundCallResponse)
async def start_outbound_call(body: VoiceOutboundCallRequest):
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_phone_number):
        raise HTTPException(status_code=422, detail="Twilio is not configured.")
    if not settings.resolved_public_base_url:
        raise HTTPException(status_code=422, detail="PUBLIC_BASE_URL or BACKEND_PUBLIC_URL is required for outbound calls.")

    session = store.get_session(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {body.session_id} not found.")
    if session.session_type != body.mode:
        raise HTTPException(status_code=422, detail=f"Session {body.session_id} is {session.session_type}, not {body.mode}.")

    if body.mode == "intake":
        webhook_url = _absolute_url("/voice/intake/start", {"session_id": body.session_id})
    else:
        webhook_url = _absolute_url("/voice/followup/start", {"session_id": body.session_id})

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Calls.json"
    async with httpx.AsyncClient(auth=(settings.twilio_account_sid, settings.twilio_auth_token), timeout=20) as client:
        response = await client.post(
            url,
            data={
                "To": body.to_phone,
                "From": settings.twilio_phone_number,
                "Url": webhook_url,
                "Method": "POST",
            },
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Twilio outbound call failed: {response.text}")

    payload = response.json()
    return VoiceOutboundCallResponse(
        queued=True,
        call_sid=payload.get("sid"),
        session_id=body.session_id,
        mode=body.mode,
        to_phone=body.to_phone,
        webhook_url=webhook_url,
    )


@router.get("/test-twiml")
def test_twiml():
    return _twiml_response("This is a sample PrelimMD TwiML response.", hangup=True)


# ════════════════════════════════════════════════════════════════════════════
# Core call handling
# ════════════════════════════════════════════════════════════════════════════

async def _handle_answer(request: Request, mode: str, explicit_call_sid: str | None):
    twilio = await _incoming_params(request)
    call_sid = twilio.get("CallSid") or explicit_call_sid
    if not call_sid:
        raise HTTPException(status_code=422, detail="CallSid is required.")

    call_session = store.get_voice_call_session(call_sid)
    if not call_session or call_session.mode != mode:
        raise HTTPException(status_code=404, detail=f"Voice call session {call_sid} not found.")

    session = store.get_session(call_session.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {call_session.session_id} not found.")

    speech = (twilio.get("SpeechResult") or "").strip()

    if call_session.completed:
        return _twiml_response("This call has already been completed. Goodbye.", hangup=True)

    if not speech:
        return _handle_no_speech(call_session=call_session, session=session, mode=mode)

    store.update_voice_call_session(call_sid, {"retry_count": 0})
    _append_patient_turn(session.session_id, speech)

    if call_session.verification_state == "pending_name":
        return _handle_name_verification(call_session=call_session, session=session, speech=speech, mode=mode)
    if call_session.verification_state == "pending_dob":
        return _handle_dob_verification(call_session=call_session, session=session, speech=speech, mode=mode)

    if mode == "intake":
        return _handle_intake_question(call_session=call_session, session=session, speech=speech)
    return _handle_followup_question(call_session=call_session, session=session, speech=speech)


def _handle_no_speech(call_session: VoiceCallSession, session: IntakeCallSession, mode: str):
    if call_session.retry_count >= 1:
        prompt = "No worries. We weren't able to complete this call today. Your care team may follow up later."
        _append_ai_turn(session.session_id, prompt)
        _finish_call(
            call_session=call_session,
            session=session,
            reason="no_speech_incomplete",
            session_status="abandoned",
        )
        return _twiml_response(prompt, hangup=True)

    prompt = "Sorry, I didn't catch that. Could you say that again?"
    _append_ai_turn(session.session_id, prompt)
    store.update_voice_call_session(call_session.call_sid, {"retry_count": call_session.retry_count + 1})
    return _gather_response(prompt, action_path=f"/voice/{mode}/answer", query={"call_sid": call_session.call_sid})


def _handle_name_verification(call_session: VoiceCallSession, session: IntakeCallSession, speech: str, mode: str):
    patient = store.get_patient(session.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {session.patient_id} not found.")

    lowered = _normalize_text(speech)
    attempts = call_session.verification_name_attempts + 1

    if _matches_any(lowered, WRONG_PATIENT_PATTERNS):
        prompt = "Thank you for letting me know. I won't continue this call."
        _append_ai_turn(session.session_id, prompt)
        _finish_call(call_session, session, reason="verification_failed", session_status="abandoned", extra_flags=["verification_failed"])
        return _twiml_response(prompt, hangup=True)

    if _name_matches(speech, patient.full_name):
        prompt = "Thanks, I got that. Now please say your date of birth, for example March 14 1985."
        _append_ai_turn(session.session_id, prompt, ["date_of_birth"])
        store.update_voice_call_session(
            call_session.call_sid,
            {
                "verification_state": "pending_dob",
                "verification_name": speech,
                "verification_name_attempts": attempts,
            },
        )
        return _gather_response(prompt, action_path=f"/voice/{mode}/answer", query={"call_sid": call_session.call_sid})

    if attempts >= 2:
        prompt = "I'm sorry, we couldn't verify your identity. Please contact the clinic directly, and your care team may follow up later."
        _append_ai_turn(session.session_id, prompt)
        _finish_call(call_session, session, reason="verification_failed", session_status="abandoned", extra_flags=["verification_failed"])
        return _twiml_response(prompt, hangup=True)

    prompt = "I'm sorry, I couldn't match that name. Please say your full name again."
    _append_ai_turn(session.session_id, prompt, ["full_name"])
    store.update_voice_call_session(call_session.call_sid, {"verification_name_attempts": attempts})
    return _gather_response(prompt, action_path=f"/voice/{mode}/answer", query={"call_sid": call_session.call_sid})


def _handle_dob_verification(call_session: VoiceCallSession, session: IntakeCallSession, speech: str, mode: str):
    patient = store.get_patient(session.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {session.patient_id} not found.")

    attempts = call_session.verification_dob_attempts + 1
    parsed_dob = _parse_dob(speech)

    if parsed_dob == patient.date_of_birth:
        store.update_voice_call_session(
            call_session.call_sid,
            {"verification_state": "verified", "verification_dob_attempts": attempts},
        )
        if mode == "intake":
            prompt = _next_intake_prompt(session)
        else:
            prompt = _next_followup_prompt(session)

        _append_ai_turn(session.session_id, prompt)
        if _is_completion_prompt(prompt):
            _finish_call(call_session, session, reason="completed", session_status="completed")
            return _twiml_response(prompt, hangup=True)
        return _gather_response(prompt, action_path=f"/voice/{mode}/answer", query={"call_sid": call_session.call_sid})

    if attempts >= 2:
        prompt = "I'm sorry, we couldn't verify your identity. Please contact the clinic directly, and your care team may follow up later."
        _append_ai_turn(session.session_id, prompt)
        _finish_call(call_session, session, reason="verification_failed", session_status="abandoned", extra_flags=["verification_failed"])
        return _twiml_response(prompt, hangup=True)

    prompt = "I couldn't match that date of birth. Please say your date of birth again, including the month, day, and year."
    _append_ai_turn(session.session_id, prompt, ["date_of_birth"])
    store.update_voice_call_session(call_session.call_sid, {"verification_dob_attempts": attempts})
    return _gather_response(prompt, action_path=f"/voice/{mode}/answer", query={"call_sid": call_session.call_sid})


def _handle_intake_question(call_session: VoiceCallSession, session: IntakeCallSession, speech: str):
    field = _current_intake_field(session)
    if not field:
        prompt = "Thanks again. That's everything I needed for today. Goodbye."
        _append_ai_turn(session.session_id, prompt)
        _finish_call(call_session, session, reason="completed", session_status="completed")
        return _twiml_response(prompt, hangup=True)

    classification = _classify_answer(speech, concerning_keywords=[])
    if classification["wrong_patient"]:
        prompt = "Thank you for letting me know. I won't continue this call."
        _append_ai_turn(session.session_id, prompt)
        _finish_call(call_session, session, reason="verification_failed", session_status="abandoned", extra_flags=["verification_failed"])
        return _twiml_response(prompt, hangup=True)

    if classification["unclear"] and call_session.clarification_attempts < 1:
        prompt = f"No problem, let me ask that another way. {field.question}"
        _append_ai_turn(session.session_id, prompt, [field.field_id])
        store.update_voice_call_session(
            call_session.call_sid,
            {
                "clarification_attempts": call_session.clarification_attempts + 1,
                "unclear_count": call_session.unclear_count + 1,
            },
        )
        return _gather_response(prompt, action_path="/voice/intake/answer", query={"call_sid": call_session.call_sid})

    stored_value = "patient declined" if classification["declined"] else ("unclear" if classification["unclear"] else speech)
    flags = []
    if classification["medical_advice"]:
        flags.append("medical_advice_requested")
    if classification["concerning"]:
        flags.append(f"concerning_response:{field.field_id}")

    _store_session_answer(session=session, key=field.field_id, value=stored_value, flags=flags)
    updated_session = store.get_session(session.session_id)
    if not updated_session:
        raise HTTPException(status_code=500, detail="Session update failed.")

    store.update_voice_call_session(
        call_session.call_sid,
        {
            "current_question_index": call_session.current_question_index + 1,
            "clarification_attempts": 0,
        },
    )

    next_field = _current_intake_field(updated_session)
    prompt = _build_next_prompt(
        next_question=next_field.question if next_field else None,
        medical_advice=classification["medical_advice"],
        concerning=classification["concerning"],
        done=next_field is None,
        closing="That's everything I needed for today. Goodbye.",
    )
    _append_ai_turn(updated_session.session_id, prompt, [next_field.field_id] if next_field else [])

    if next_field is None:
        _finish_call(call_session, updated_session, reason="completed", session_status="completed")
        return _twiml_response(prompt, hangup=True)
    return _gather_response(prompt, action_path="/voice/intake/answer", query={"call_sid": call_session.call_sid})


def _handle_followup_question(call_session: VoiceCallSession, session: IntakeCallSession, speech: str):
    task = store.get_followup_task(session.task_id) if session.task_id else None
    if not task:
        raise HTTPException(status_code=404, detail="Follow-up task not found.")

    if call_session.current_question_index >= len(task.questions):
        prompt = "Thank you for speaking with us today. I'll share this update with your care team. Goodbye."
        _append_ai_turn(session.session_id, prompt)
        _finish_call(call_session, session, reason="completed", session_status="completed")
        return _twiml_response(prompt, hangup=True)

    question = task.questions[call_session.current_question_index]
    classification = _classify_answer(speech, concerning_keywords=question.concerning_keywords)

    if classification["unclear"] and call_session.clarification_attempts < 1:
        prompt = f"No problem, let me ask that another way. {question.text}"
        _append_ai_turn(session.session_id, prompt, [question.question_id])
        store.update_voice_call_session(
            call_session.call_sid,
            {
                "clarification_attempts": call_session.clarification_attempts + 1,
                "unclear_count": call_session.unclear_count + 1,
            },
        )
        return _gather_response(prompt, action_path="/voice/followup/answer", query={"call_sid": call_session.call_sid})

    stored_value = "patient declined" if classification["declined"] else ("unclear" if classification["unclear"] else speech)
    flags = []
    if classification["medical_advice"]:
        flags.append("medical_advice_requested")
    if classification["concerning"]:
        flags.append(f"concerning_response:{question.question_id}")

    _store_session_answer(session=session, key=question.question_id, value=stored_value, flags=flags)
    store.save_followup_response(
        FollowUpResponse(
            response_id=store.new_id("fur-"),
            task_id=task.task_id,
            question_id=question.question_id,
            answer=stored_value,
            flagged=classification["medical_advice"] or classification["concerning"],
            flag_reason=", ".join(flags) if flags else None,
            timestamp=store.now_iso(),
        )
    )

    updated_session = store.get_session(session.session_id)
    if not updated_session:
        raise HTTPException(status_code=500, detail="Session update failed.")

    next_index = call_session.current_question_index + 1
    store.update_voice_call_session(
        call_session.call_sid,
        {
            "current_question_index": next_index,
            "clarification_attempts": 0,
        },
    )

    remaining_question = task.questions[next_index] if next_index < len(task.questions) else None
    prompt = _build_next_prompt(
        next_question=remaining_question.text if remaining_question else None,
        medical_advice=classification["medical_advice"],
        concerning=classification["concerning"],
        done=remaining_question is None,
        closing="Thank you for speaking with us today. I'll share this update with your care team. Goodbye.",
    )
    _append_ai_turn(updated_session.session_id, prompt, [remaining_question.question_id] if remaining_question else [])

    if remaining_question is None:
        _finish_call(call_session, updated_session, reason="completed", session_status="completed")
        return _twiml_response(prompt, hangup=True)
    return _gather_response(prompt, action_path="/voice/followup/answer", query={"call_sid": call_session.call_sid})


# ════════════════════════════════════════════════════════════════════════════
# Session / store helpers
# ════════════════════════════════════════════════════════════════════════════

def _resolve_intake_session(session_id: str | None, visit_id: str | None) -> IntakeCallSession:
    if session_id:
        session = store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
        if session.session_type != "intake":
            raise HTTPException(status_code=422, detail=f"Session {session_id} is not an intake session.")
        return session

    if not visit_id:
        raise HTTPException(status_code=422, detail="session_id or visit_id is required.")

    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")

    assignments = store.get_assignments_for_visit(visit_id)
    if not assignments:
        raise HTTPException(
            status_code=404,
            detail=f"No forms assigned to visit {visit_id}. Assign forms and run POST /intake/prefill/{visit_id} first.",
        )

    return interview_engine.start_intake_session(
        visit_id=visit_id,
        patient_id=visit.patient_id,
        missing_fields=_intake_fields_for_visit(visit_id),
    )


def _resolve_followup_session(session_id: str | None, task_id: str | None) -> IntakeCallSession:
    if session_id:
        session = store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
        if session.session_type != "followup":
            raise HTTPException(status_code=422, detail=f"Session {session_id} is not a follow-up session.")
        return session

    if not task_id:
        raise HTTPException(status_code=422, detail="session_id or task_id is required.")

    task = store.get_followup_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Follow-up task {task_id} not found.")

    return interview_engine.start_followup_session(task_id)


def _load_or_create_call_session(
    call_sid: str,
    session: IntakeCallSession,
    mode: str,
    from_phone: str | None,
    to_phone: str | None,
):
    existing = store.get_voice_call_session(call_sid)
    if existing:
        return existing, False

    call_session = VoiceCallSession(
        call_sid=call_sid,
        session_id=session.session_id,
        mode=mode,
        patient_id=session.patient_id,
        visit_id=session.visit_id,
        task_id=session.task_id,
        from_phone=from_phone,
        to_phone=to_phone,
        current_question_index=session.current_question_index,
        created_at=store.now_iso(),
        updated_at=store.now_iso(),
    )
    store.save_voice_call_session(call_session)
    return call_session, True


def _store_session_answer(session: IntakeCallSession, key: str, value: str, flags: list[str]):
    collected = dict(session.collected_answers)
    collected[key] = value

    combined_flags = list(session.flags)
    for flag in flags:
        if flag not in combined_flags:
            combined_flags.append(flag)

    updates = {
        "collected_answers": collected,
        "flags": combined_flags,
        "current_question_index": session.current_question_index + 1,
    }
    store.update_session(session.session_id, updates)

    if session.task_id:
        task = store.get_followup_task(session.task_id)
        if task:
            task_flags = list(task.flags)
            for flag in flags:
                if flag not in task_flags:
                    task_flags.append(flag)
            store.update_followup_task(task.task_id, {"flags": task_flags, "status": "in_progress"})


def _finish_call(
    call_session: VoiceCallSession,
    session: IntakeCallSession,
    reason: str,
    session_status: str,
    extra_flags: list[str] | None = None,
):
    flags = list(session.flags)
    for flag in extra_flags or []:
        if flag not in flags:
            flags.append(flag)

    store.update_session(
        session.session_id,
        {
            "status": session_status,
            "completed_at": store.now_iso(),
            "flags": flags,
        },
    )
    store.update_voice_call_session(
        call_session.call_sid,
        {
            "completed": True,
            "completion_reason": reason,
            "verification_state": "failed" if reason == "verification_failed" else call_session.verification_state,
        },
    )

    if session.task_id:
        task_status = "completed" if session_status == "completed" else "failed"
        summary = "Completed by Twilio voice call." if task_status == "completed" else f"Ended early: {reason}."
        store.update_followup_task(
            session.task_id,
            {
                "status": task_status,
                "results_summary": summary,
                "flags": flags,
            },
        )


def _append_patient_turn(session_id: str, content: str):
    session = store.get_session(session_id)
    if not session:
        return
    turn = {
        "turn_id": store.new_id("t-"),
        "role": "patient",
        "content": content,
        "timestamp": store.now_iso(),
        "field_ids_targeted": [],
    }
    store.update_session(session_id, {"conversation": [*session.conversation, turn]})


def _append_ai_turn(session_id: str, content: str, field_ids: list[str] | None = None):
    session = store.get_session(session_id)
    if not session:
        return
    turn = {
        "turn_id": store.new_id("t-"),
        "role": "ai",
        "content": content,
        "timestamp": store.now_iso(),
        "field_ids_targeted": field_ids or [],
    }
    store.update_session(session_id, {"conversation": [*session.conversation, turn]})


# ════════════════════════════════════════════════════════════════════════════
# Question helpers
# ════════════════════════════════════════════════════════════════════════════

def _intake_fields_for_visit(visit_id: str) -> list[MissingField]:
    fields: list[MissingField] = []
    visit = store.get_visit(visit_id)
    if not visit:
        return fields
    for assignment in store.get_assignments_for_visit(visit_id):
        template = store.get_template(assignment.template_id)
        if not template:
            continue
        form_id = assignment.form_id or assignment.assignment_id
        prefilled = ai_engine.get_prefilled_form(form_id)
        if not prefilled:
            prefilled = ai_engine.local_prefill(
                FormSchema(
                    form_id=form_id,
                    form_name=template.name,
                    fields=template.fields,
                ),
                visit.patient_id,
                visit_id=visit.visit_id,
            )
        if not prefilled:
            continue
        for field in prefilled.missing_fields:
            if field.field_id not in PHONE_BLOCKLIST:
                fields.append(field)
    return fields


def _current_intake_field(session: IntakeCallSession) -> MissingField | None:
    if not session.visit_id:
        return None
    for field in _intake_fields_for_visit(session.visit_id):
        if field.field_id not in session.collected_answers:
            return field
    return None


def _next_intake_prompt(session: IntakeCallSession) -> str:
    field = _current_intake_field(session)
    if field:
        return f"Thanks, you're verified. {field.question}"
    return "Thanks, you're verified. We don't have any remaining intake questions today. Goodbye."


def _next_followup_prompt(session: IntakeCallSession) -> str:
    if not session.task_id:
        return "Thanks, you're verified. We don't have any follow-up questions today. Goodbye."
    task = store.get_followup_task(session.task_id)
    if task and session.current_question_index < len(task.questions):
        return f"Thanks, you're verified. {task.questions[session.current_question_index].text}"
    return "Thanks, you're verified. We don't have any follow-up questions today. Goodbye."


def _build_next_prompt(next_question: str | None, medical_advice: bool, concerning: bool, done: bool, closing: str) -> str:
    parts = []
    if medical_advice:
        parts.append("I can't provide medical advice, but I can pass this question to your care team so they can follow up.")
    elif concerning:
        parts.append("Thank you for telling me. I'll make sure your care team sees this update.")
    else:
        parts.append("Thanks, I got that.")

    if done:
        parts.append(closing)
    elif next_question:
        parts.append(next_question)

    return " ".join(parts).strip()


# ════════════════════════════════════════════════════════════════════════════
# TwiML / audio helpers
# ════════════════════════════════════════════════════════════════════════════

def _gather_response(prompt: str, action_path: str, query: dict[str, str] | None = None):
    root = ET.Element("Response")
    gather = ET.SubElement(
        root,
        "Gather",
        {
            "input": "speech",
            "method": "POST",
            "speechTimeout": "auto",
            "timeout": "5",
            "action": _absolute_url(action_path, query),
        },
    )

    audio_url = _maybe_persist_tts(prompt)
    if audio_url:
        ET.SubElement(gather, "Play").text = audio_url
    else:
        say = ET.SubElement(gather, "Say", {"voice": TWILIO_SAY_VOICE})
        say.text = prompt

    return _xml_response(root)


def _twiml_response(prompt: str, hangup: bool = False):
    root = ET.Element("Response")
    audio_url = _maybe_persist_tts(prompt)
    if audio_url:
        ET.SubElement(root, "Play").text = audio_url
    else:
        say = ET.SubElement(root, "Say", {"voice": TWILIO_SAY_VOICE})
        say.text = prompt
    if hangup:
        ET.SubElement(root, "Hangup")
    return _xml_response(root)


def _xml_response(root: ET.Element):
    xml_body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(content=xml_body, media_type="application/xml")


def _maybe_persist_tts(text: str) -> str | None:
    if not settings.resolved_public_base_url:
        return None

    audio = tts_service.synthesize(text)
    if not audio:
        return None

    STATIC_TTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{store.new_id('tts-')}.mp3"
    path = STATIC_TTS_DIR / filename
    path.write_bytes(audio)
    return f"{settings.resolved_public_base_url}/static/tts/{filename}"


def _absolute_url(path: str, query: dict[str, str] | None = None) -> str:
    if settings.resolved_public_base_url:
        base = f"{settings.resolved_public_base_url}{path}"
    else:
        base = path
    if query:
        return f"{base}?{urlencode(query)}"
    return base


# ════════════════════════════════════════════════════════════════════════════
# Parsing / classification helpers
# ════════════════════════════════════════════════════════════════════════════

async def _incoming_params(request: Request) -> dict[str, str]:
    params = dict(request.query_params)
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload = await request.json()
            if isinstance(payload, dict):
                params.update({k: str(v) for k, v in payload.items() if v is not None})
        except Exception:
            pass
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        params.update({k: str(v) for k, v in form.items()})
    return params


def _classify_answer(speech: str, concerning_keywords: list[str]) -> dict[str, bool]:
    lowered = _normalize_text(speech)
    all_concern_keywords = [*concerning_keywords, *GLOBAL_CONCERN_KEYWORDS]
    return {
        "declined": _matches_any(lowered, DECLINE_PATTERNS),
        "unclear": _matches_any(lowered, UNCLEAR_PATTERNS),
        "wrong_patient": _matches_any(lowered, WRONG_PATIENT_PATTERNS),
        "medical_advice": _matches_any(lowered, MEDICAL_ADVICE_PATTERNS),
        "concerning": _matches_any(lowered, all_concern_keywords),
    }


def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9\s/,-]", " ", text.lower()).strip()


def _matches_any(text: str, patterns) -> bool:
    return any(pattern in text for pattern in patterns)


def _name_matches(spoken_name: str, expected_name: str) -> bool:
    expected_tokens = [token for token in _normalize_text(expected_name).split() if token]
    spoken = _normalize_text(spoken_name)
    return all(token in spoken for token in expected_tokens)


def _parse_dob(text: str) -> str | None:
    cleaned = _normalize_text(text).replace(",", " ").replace("-", "/")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    numeric_match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", cleaned)
    if numeric_match:
        month, day, year = numeric_match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    numeric_match = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", cleaned)
    if numeric_match:
        year, month, day = numeric_match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    month_map = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    for month_name, month_num in month_map.items():
        match = re.search(rf"{month_name}\s+(\d{{1,2}})\s+(\d{{4}})", cleaned)
        if match:
            day, year = match.groups()
            return f"{year}-{month_num}-{int(day):02d}"

    return None


def _is_completion_prompt(prompt: str) -> bool:
    return "we don't have any" in prompt.lower() or prompt.lower().endswith("goodbye.")
