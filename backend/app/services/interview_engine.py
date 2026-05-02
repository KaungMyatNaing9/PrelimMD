# app/services/interview_engine.py
# Reusable session orchestration engine for both intake and follow-up calls.
#
# Supports two session types:
#   "intake"   — collects missing fields from a prefilled intake form
#   "followup" — walks through a doctor-configured question list and flags concerns
#
# Safety rules enforced in all AI responses:
#   - Never diagnose or recommend treatment
#   - Never advise on starting/stopping/changing medication
#   - Never deeply interpret lab results
#   - If patient asks for medical advice → redirect to care team
#   - If concerning symptoms detected → flag and acknowledge without alarming

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from app.config import settings
from app.models.schemas import (
    AnswerResponse,
    FollowUpQuestion,
    IntakeCallSession,
    MissingField,
    SessionTurn,
)
from app.services import store

logger = logging.getLogger(__name__)


# ── OpenAI helper ─────────────────────────────────────────────────────────────

def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _chat(system: str, user: str, model: str = "gpt-4o") -> str:
    response = _client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


# ── Safety system prompt (appended to all AI calls) ───────────────────────────

_SAFETY_RULES = """
SAFETY RULES — follow these without exception:
- You are NOT a doctor. Never diagnose, suggest a diagnosis, or recommend a treatment.
- Never tell the patient to start, stop, or change any medication.
- Never interpret lab results or imaging in clinical terms.
- If the patient asks a medical question, say:
  "I can't provide medical advice, but I can pass this question to your care team so they can follow up."
- If the patient mentions a concerning or urgent symptom (chest pain, can't breathe, severe pain, bleeding),
  say: "Thank you for telling me. I'll make sure your care team sees this right away."
  Then set flagged=true in your JSON response.
- Do NOT reassure the patient that serious symptoms are probably fine.
- Store "patient declined" if the patient refuses to answer.
"""

_TONE_RULES = """
CONVERSATION STYLE:
- Warm, calm, and professional — like a skilled medical receptionist.
- Keep responses short (1-2 sentences max for acknowledgment, then the next question).
- Always acknowledge the patient's previous answer before asking the next question.
- Ask ONE question at a time.
- If the answer is unclear, ask for clarification once. If still unclear, note it and move on.
"""


# ════════════════════════════════════════════════════════════════════════════
# Intake session — collects missing fields from a prefilled form
# ════════════════════════════════════════════════════════════════════════════

_INTAKE_SYSTEM = f"""
You are a pre-visit intake assistant for a medical clinic.
You are conducting a short phone call to collect missing information from a patient
before their upcoming appointment.

{_TONE_RULES}
{_SAFETY_RULES}

Your job: given the conversation so far and the list of fields still needed,
decide what to ask next — or declare the call complete.

Return ONLY valid JSON, no markdown:
{{
  "acknowledgment": "<1 sentence acknowledging the previous answer, or empty string for first turn>",
  "next_question": "<the next question to ask, or null if done>",
  "field_ids_targeted": ["<field_ids this question targets>"],
  "extracted": {{"field_id": "value"}},
  "done": false,
  "flagged": false,
  "flag_reason": null
}}

Rules:
- extracted: pull any field values clearly stated by the patient in their last answer.
  Only extract what was actually said — do not infer or guess.
- done: set true when all required fields are collected or the patient has declined all.
- flagged: set true if the patient mentions an urgent symptom per the safety rules.
- Never ask for SSN, signatures, or sensitive identifiers over the phone.
- Fields in the "consent" section are never asked over the phone.
""".strip()


def start_intake_session(
    visit_id: str,
    patient_id: str,
    missing_fields: List[MissingField],
) -> IntakeCallSession:
    """
    Create a new intake call session.
    Generates the opening greeting and first question.
    """
    session_id = store.new_id("sess-")
    patient = store.get_patient(patient_id)
    patient_name = patient.first_name if patient else "there"

    # Filter out phone-inappropriate fields
    _PHONE_BLOCKLIST = {"ssn", "social_security", "patient_signature", "signature", "consent_signature"}
    askable = [f for f in missing_fields if f.field_id not in _PHONE_BLOCKLIST
               and f.field_id not in ("consent_date",)]

    opening = (
        f"Hi {patient_name}, this is a quick call from your care team to gather "
        f"a few details before your upcoming appointment. This should only take a couple of minutes. "
        f"To start — can you confirm your full name and date of birth?"
    )

    session = IntakeCallSession(
        session_id=session_id,
        session_type="intake",
        visit_id=visit_id,
        patient_id=patient_id,
        status="in_progress",
        conversation=[
            SessionTurn(
                turn_id=store.new_id("t-"),
                role="ai",
                content=opening,
                timestamp=store.now_iso(),
                field_ids_targeted=["full_name", "date_of_birth"],
            )
        ],
        collected_answers={},
        flags=[],
        created_at=store.now_iso(),
        current_question_index=0,
    )

    # Store the missing fields list in a side-channel (keyed by session_id)
    _INTAKE_FIELD_CACHE[session_id] = askable

    store.save_session(session)
    return session


# Side-channel: stores the list of missing fields per session (not in the session model)
_INTAKE_FIELD_CACHE: Dict[str, List[MissingField]] = {}


def process_intake_answer(session_id: str, patient_answer: str) -> AnswerResponse:
    """
    Process one patient answer for an intake session.
    Returns the AI's next question or completion signal.
    """
    session = store.get_session(session_id)
    if not session:
        return AnswerResponse(session_id=session_id, is_done=True)

    if session.status != "in_progress":
        return AnswerResponse(session_id=session_id, is_done=True)

    missing_fields = _INTAKE_FIELD_CACHE.get(session_id, [])

    # Append patient's answer to conversation
    patient_turn = SessionTurn(
        turn_id=store.new_id("t-"),
        role="patient",
        content=patient_answer,
        timestamp=store.now_iso(),
    )
    updated_conv = list(session.conversation) + [patient_turn]

    # Build the LLM prompt
    conv_text = "\n".join(
        f"{'Assistant' if t.role == 'ai' else 'Patient'}: {t.content}"
        for t in updated_conv
    )
    already_collected = set(session.collected_answers.keys())
    remaining = [
        {"field_id": f.field_id, "label": f.label, "type": f.type, "required": f.required}
        for f in missing_fields
        if f.field_id not in already_collected
    ]

    user_msg = (
        f"Fields still needed:\n{json.dumps(remaining, indent=2)}\n\n"
        f"Conversation so far:\n{conv_text}"
    )

    raw = _chat(_INTAKE_SYSTEM, user_msg)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        result = json.loads(raw)
    except Exception:
        result = {"acknowledgment": "", "next_question": None, "field_ids_targeted": [], "extracted": {}, "done": True, "flagged": False, "flag_reason": None}

    # Merge extracted answers
    collected = dict(session.collected_answers)
    collected.update(result.get("extracted", {}))

    # Build AI turn
    ack = result.get("acknowledgment", "")
    next_q = result.get("next_question")
    ai_text = f"{ack} {next_q}".strip() if next_q else (ack or "Thank you, that's everything we need. We'll see you at your appointment!")
    is_done = result.get("done", False) or not next_q

    ai_turn = SessionTurn(
        turn_id=store.new_id("t-"),
        role="ai",
        content=ai_text,
        timestamp=store.now_iso(),
        field_ids_targeted=result.get("field_ids_targeted", []),
    )
    updated_conv.append(ai_turn)

    flags = list(session.flags)
    if result.get("flagged"):
        flag_reason = result.get("flag_reason") or "Patient mentioned concerning symptom"
        if flag_reason not in flags:
            flags.append(flag_reason)

    store.update_session(session_id, {
        "conversation": updated_conv,
        "collected_answers": collected,
        "flags": flags,
        "status": "completed" if is_done else "in_progress",
        "completed_at": store.now_iso() if is_done else None,
    })

    return AnswerResponse(
        session_id=session_id,
        next_question=ai_text if not is_done else None,
        field_ids_targeted=result.get("field_ids_targeted", []),
        is_done=is_done,
        flagged=bool(result.get("flagged")),
        flag_reason=result.get("flag_reason"),
    )


# ════════════════════════════════════════════════════════════════════════════
# Follow-up session — walks through a doctor-configured question list
# ════════════════════════════════════════════════════════════════════════════

_FOLLOWUP_SYSTEM = f"""
You are conducting a post-discharge follow-up call on behalf of a patient's care team.
You have a list of questions configured by the patient's doctor.

{_TONE_RULES}
{_SAFETY_RULES}

Your job: given the last patient answer and the next question to ask, produce a warm
response that acknowledges what the patient said and then asks the next question.

Also check if the patient's answer contains any concerning keywords and flag if needed.

Return ONLY valid JSON, no markdown:
{{
  "ai_response": "<acknowledgment + next question, or closing if done>",
  "flagged": false,
  "flag_reason": null,
  "extracted_answer": "<clean summary of patient's answer to the previous question>"
}}
""".strip()


def start_followup_session(task_id: str) -> IntakeCallSession:
    """Create a new follow-up call session from a scheduled follow-up task."""
    task = store.get_followup_task(task_id)
    if not task:
        raise ValueError(f"Follow-up task {task_id} not found")

    patient = store.get_patient(task.patient_id)
    patient_name = patient.first_name if patient else "there"

    session_id = store.new_id("sess-")
    opening = (
        f"Hi {patient_name}, this is a follow-up call from your care team. "
        f"We're checking in to see how you've been doing since your recent visit. "
        f"This will just take a few minutes — is now a good time?"
    )

    session = IntakeCallSession(
        session_id=session_id,
        session_type="followup",
        task_id=task_id,
        patient_id=task.patient_id,
        status="in_progress",
        conversation=[
            SessionTurn(
                turn_id=store.new_id("t-"),
                role="ai",
                content=opening,
                timestamp=store.now_iso(),
            )
        ],
        collected_answers={},
        flags=[],
        created_at=store.now_iso(),
        current_question_index=0,
    )

    store.save_session(session)
    store.update_followup_task(task_id, {"status": "in_progress", "session_id": session_id})
    return session


def process_followup_answer(session_id: str, patient_answer: str) -> AnswerResponse:
    """
    Process one patient answer for a follow-up session.
    Advances through the question list and flags concerning responses.
    """
    session = store.get_session(session_id)
    if not session or not session.task_id:
        return AnswerResponse(session_id=session_id, is_done=True)

    task = store.get_followup_task(session.task_id)
    if not task:
        return AnswerResponse(session_id=session_id, is_done=True)

    questions = task.questions
    q_index = session.current_question_index

    # Append patient's answer
    patient_turn = SessionTurn(
        turn_id=store.new_id("t-"),
        role="patient",
        content=patient_answer,
        timestamp=store.now_iso(),
    )
    updated_conv = list(session.conversation) + [patient_turn]

    # Determine next question
    next_q_index = q_index + 1  # first answer advances past question 0 (opening), but opening wasn't a real question
    # q_index 0 = just gave consent to talk → ask first question
    # q_index N = just answered question N-1 → ask question N

    # The opening was index 0 (not a real question), so first real Q is at questions[0]
    # q_index tracks how many patient answers we've received (including consent)
    real_q_idx = q_index  # map patient answer index to question index

    is_done = real_q_idx >= len(questions)
    next_question: Optional[FollowUpQuestion] = None if is_done else questions[real_q_idx]

    # Build LLM context
    prev_question_text = (
        questions[real_q_idx - 1].text if real_q_idx > 0 and real_q_idx - 1 < len(questions)
        else "How are you doing overall?"
    )
    next_q_text = next_question.text if next_question else None

    user_msg = json.dumps({
        "previous_question": prev_question_text,
        "patient_answer": patient_answer,
        "next_question_to_ask": next_q_text,
        "is_last_question": is_done or (real_q_idx == len(questions) - 1),
        "concerning_keywords_for_previous_q": (
            questions[real_q_idx - 1].concerning_keywords
            if real_q_idx > 0 and real_q_idx - 1 < len(questions)
            else []
        ),
    })

    raw = _chat(_FOLLOWUP_SYSTEM, user_msg)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        result = json.loads(raw)
    except Exception:
        result = {
            "ai_response": next_q_text or "Thank you so much for taking the time to speak with us today. Your care team will review everything.",
            "flagged": False,
            "flag_reason": None,
            "extracted_answer": patient_answer,
        }

    ai_text = result.get("ai_response", "")
    if not ai_text:
        ai_text = next_q_text or "Thank you for sharing. Your care team will follow up soon."

    ai_turn = SessionTurn(
        turn_id=store.new_id("t-"),
        role="ai",
        content=ai_text,
        timestamp=store.now_iso(),
        field_ids_targeted=[next_question.question_id] if next_question else [],
    )
    updated_conv.append(ai_turn)

    # Store extracted answer keyed by the question that was just answered
    collected = dict(session.collected_answers)
    if real_q_idx > 0:
        prev_q = questions[real_q_idx - 1]
        collected[prev_q.question_id] = result.get("extracted_answer", patient_answer)

    flags = list(session.flags)
    if result.get("flagged"):
        flag_reason = result.get("flag_reason") or "Patient mentioned concerning symptom"
        if flag_reason not in flags:
            flags.append(flag_reason)

    # On completion also check if last question was just answered
    final_done = is_done or (not next_question)

    store.update_session(session_id, {
        "conversation": updated_conv,
        "collected_answers": collected,
        "flags": flags,
        "current_question_index": q_index + 1,
        "status": "completed" if final_done else "in_progress",
        "completed_at": store.now_iso() if final_done else None,
    })

    if final_done:
        store.update_followup_task(session.task_id, {
            "status": "completed",
            "flags": flags,
            "results_summary": f"Completed {real_q_idx} question(s). Flags: {'; '.join(flags) if flags else 'none'}.",
        })

    return AnswerResponse(
        session_id=session_id,
        next_question=ai_text if not final_done else None,
        field_ids_targeted=[next_question.question_id] if next_question else [],
        is_done=final_done,
        flagged=bool(result.get("flagged")),
        flag_reason=result.get("flag_reason"),
    )


# ════════════════════════════════════════════════════════════════════════════
# Shared: complete a session
# ════════════════════════════════════════════════════════════════════════════

def complete_session(session_id: str) -> Optional[IntakeCallSession]:
    """Mark a session as completed (can be called early to abandon gracefully)."""
    session = store.get_session(session_id)
    if not session:
        return None

    store.update_session(session_id, {
        "status": "completed",
        "completed_at": store.now_iso(),
    })

    # If follow-up, mark task completed too
    if session.task_id:
        task = store.get_followup_task(session.task_id)
        if task and task.status == "in_progress":
            store.update_followup_task(session.task_id, {"status": "completed"})

    return store.get_session(session_id)
