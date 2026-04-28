# app/services/ai_engine.py
# LLM-driven clinical interview engine.
#
# Each session walks a patient through a loaded FormSchema using GPT-4o.
# The LLM returns structured InterviewTurn objects so answers are mapped back
# to specific question IDs and scoring is computed deterministically.
#
# Session state is stored in-memory (dict keyed by session_id) for the MVP.

import json
import textwrap
import uuid
from pathlib import Path
from typing import Any, Optional

from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import (
    FormSchema,
    InterviewTurn,
    QuestionSchema,
    ScoringRange,
    SessionSummary,
    TranscriptMessage,
    TriageLevel,
)

# ── In-memory session store ───────────────────────────────────────────────────

_SESSIONS: dict[str, "_SessionState"] = {}

# Directory where pre-converted form JSON files live
_FORMS_DIR = Path(__file__).parent.parent / "forms"

# Runtime-registered forms (uploaded via the clinician upload endpoint)
_DYNAMIC_FORMS: dict[str, FormSchema] = {}

# Red-flag patterns that always raise an emergency triage flag
_EMERGENCY_PATTERNS = [
    "can't breathe", "cannot breathe", "can not breathe",
    "trouble breathing", "difficulty breathing",
    "chest pain", "chest pressure", "chest tightness",
    "passed out", "passing out", "fainted", "fainting",
    "stroke", "unresponsive", "unconscious",
    "severe bleeding", "coughing blood", "vomiting blood",
    "suicidal", "suicide", "kill myself", "hurt myself",
]


class _SessionState:
    def __init__(self, session_id: str, form: FormSchema) -> None:
        self.session_id = session_id
        self.form = form
        self.status: str = "in_progress"
        self.answers: dict[str, Any] = {}
        self.transcript: list[TranscriptMessage] = []
        self.scores: dict[str, int] = {}
        self.triage_flags: list[str] = []

        # Flat ordered list of all questions across all sections
        self.all_questions: list[QuestionSchema] = [
            q
            for section in form.sections
            for q in section.questions
        ]
        self.question_index_map: dict[str, int] = {
            q.id: i for i, q in enumerate(self.all_questions)
        }
        self.current_question_index: int = 0

    @property
    def current_question(self) -> Optional[QuestionSchema]:
        if self.current_question_index < len(self.all_questions):
            return self.all_questions[self.current_question_index]
        return None

    @property
    def total_questions(self) -> int:
        return len(self.all_questions)

    @property
    def progress(self) -> float:
        if not self.all_questions:
            return 1.0
        return min(self.current_question_index / len(self.all_questions), 1.0)

    def advance_to_next(self, skip_question_ids: Optional[list[str]] = None) -> None:
        """Move to the next unanswered, non-skipped question."""
        self.current_question_index += 1
        skip_set = set(skip_question_ids or [])
        while (
            self.current_question_index < len(self.all_questions)
            and (
                self.all_questions[self.current_question_index].id in self.answers
                or self.all_questions[self.current_question_index].id in skip_set
            )
        ):
            self.current_question_index += 1

    def questions_answered(self) -> int:
        return len(self.answers)

    def compute_section_score(self, section_id: str) -> int:
        section = next((s for s in self.form.sections if s.id == section_id), None)
        if section is None:
            return 0
        total = 0
        for q in section.questions:
            answer = self.answers.get(q.id)
            if answer is not None and isinstance(answer, (int, float)):
                total += int(answer) * q.scoring_weight
        return total

    def compute_triage_level(self) -> TriageLevel:
        if self.triage_flags:
            return "emergency"

        if not self.form.scoring.enabled:
            return "low"

        # Sum scores across all sections
        total_score = sum(
            self.compute_section_score(s.id) for s in self.form.sections
        )

        best: Optional[ScoringRange] = None
        for scoring_range in self.form.scoring.ranges:
            if scoring_range.min <= total_score <= scoring_range.max:
                best = scoring_range
                break

        if best is None:
            return "low"
        return best.triage_level


# ── Form loader ───────────────────────────────────────────────────────────────

def register_form(form: FormSchema) -> str:
    """Register an uploaded form in the dynamic in-memory store. Returns form_id."""
    _DYNAMIC_FORMS[form.form_id] = form
    return form.form_id


def load_form(form_id: str) -> FormSchema:
    """Load a FormSchema, checking dynamically registered forms before disk."""
    if form_id in _DYNAMIC_FORMS:
        return _DYNAMIC_FORMS[form_id]
    form_path = _FORMS_DIR / f"{form_id}.json"
    if not form_path.exists():
        available = list(_DYNAMIC_FORMS.keys()) + [p.stem for p in _FORMS_DIR.glob("*.json")]
        raise ValueError(
            f"Form '{form_id}' not found. Available forms: {available}"
        )
    with form_path.open() as f:
        return FormSchema.model_validate(json.load(f))


def list_forms() -> list[dict]:
    """Return a brief listing of all available form IDs and titles."""
    forms = []
    for form in _DYNAMIC_FORMS.values():
        forms.append({
            "form_id": form.form_id,
            "title": form.title,
            "description": form.description,
        })
    for path in sorted(_FORMS_DIR.glob("*.json")):
        try:
            with path.open() as f:
                data = json.load(f)
            forms.append({
                "form_id": data.get("form_id", path.stem),
                "title": data.get("title", ""),
                "description": data.get("description", ""),
            })
        except Exception:
            pass
    return forms


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(state: _SessionState) -> str:
    current = state.current_question

    # Next question is one index ahead of the current position
    next_idx = state.current_question_index + 1
    next_question = (
        state.all_questions[next_idx]
        if next_idx < len(state.all_questions)
        else None
    )

    # All questions still ahead (starting after current) for broad context
    upcoming = state.all_questions[next_idx:]
    upcoming_summary = json.dumps(
        [
            {
                "id": q.id,
                "text": q.text,
                "hint": q.conversational_hint or q.text,
                "type": q.type,
                "options": [o.model_dump() for o in q.options],
                "required": q.required,
            }
            for q in upcoming
        ],
        indent=2,
    )

    answered_summary = json.dumps(
        {qid: val for qid, val in state.answers.items()},
        indent=2,
    )

    def _q_json(q: Optional[QuestionSchema]) -> str:
        if q is None:
            return "null"
        return json.dumps({
            "id": q.id,
            "text": q.text,
            "hint": q.conversational_hint or q.text,
            "type": q.type,
            "options": [o.model_dump() for o in q.options],
        }, indent=2)

    next_question_block = (
        _q_json(next_question)
        if next_question
        else "null — this was the last question. Set form_complete=true and give a warm closing."
    )

    return textwrap.dedent(f"""
        You are PrelimMD, a warm and professionally calm clinical intake assistant.
        You are conducting a structured patient intake interview for a clinician.

        Your current form: "{state.form.title}"
        Session ID: {state.session_id}
        Progress: {state.questions_answered()} of {state.total_questions} questions answered.

        Already answered (do not re-ask these):
        {answered_summary}

        Question the patient is answering right now:
        {_q_json(current) if current else "null — all questions have been answered"}

        Next question to ask in your ai_response:
        {next_question_block}

        All upcoming questions for context (do not skip ahead):
        {upcoming_summary}

        INSTRUCTIONS:
        1. In ai_response: briefly acknowledge the patient's answer to the current question,
           then immediately ask the NEXT question using its "hint" as your phrasing guide.
           Never end ai_response without asking the next question — do not say "let's continue"
           or similar without actually posing the question. If next question is null, give a
           warm closing statement and set form_complete=true.
        2. Extract the patient's answer and map it to the current question's type:
           - scale / single_choice: return the numeric value or option value
           - multi_choice: return a list of selected option values
           - yes_no: return "yes" or "no"
           - free_text: return the patient's answer as a trimmed string
           - numeric: return the numeric value
        3. If the patient's answer is unclear, ask a brief clarifying follow-up before advancing.
        4. Raise triage_flag=true if the patient mentions ANY of: chest pain, trouble breathing,
           cannot breathe, passed out, fainting, stroke, unresponsive, suicidal thoughts,
           severe bleeding, or coughing/vomiting blood. Set triage_reason to the specific phrase.
        5. Never skip a required question without a reason.
        6. When all questions are answered, set form_complete=true.
        7. Always return a JSON object matching the schema below exactly — no extra keys.

        Required JSON output schema:
        {{
          "ai_response": "string — acknowledgment of current answer + the next question asked",
          "question_answered_id": "string — the id of the question just answered",
          "extracted_value": "any — parsed answer value",
          "next_question_id": "string or null — the id of the next question (from next question block)",
          "triage_flag": false,
          "triage_reason": null,
          "form_complete": false
        }}
    """).strip()


# ── LLM call ──────────────────────────────────────────────────────────────────

async def _call_llm(state: _SessionState) -> InterviewTurn:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    system_prompt = _build_system_prompt(state)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in state.transcript:
        messages.append({"role": msg.role, "content": msg.content})

    response = await client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=messages,
        temperature=0.4,
    )

    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)

    return InterviewTurn(
        ai_response=data.get("ai_response", ""),
        question_answered_id=data.get("question_answered_id", ""),
        extracted_value=data.get("extracted_value"),
        next_question_id=data.get("next_question_id"),
        triage_flag=bool(data.get("triage_flag", False)),
        triage_reason=data.get("triage_reason"),
        form_complete=bool(data.get("form_complete", False)),
    )


def _keyword_triage_check(text: str) -> Optional[str]:
    """Fast keyword scan — flag emergencies without waiting for LLM."""
    lower = text.lower()
    for phrase in _EMERGENCY_PATTERNS:
        if phrase in lower:
            return phrase
    return None


# ── Public API ────────────────────────────────────────────────────────────────

async def start_session(form_id: str) -> tuple[str, str, int]:
    """
    Create a new interview session for the given form.

    Returns (session_id, first_question_text, total_questions).
    """
    form = load_form(form_id)
    session_id = str(uuid.uuid4())
    state = _SessionState(session_id, form)
    _SESSIONS[session_id] = state

    if not state.all_questions:
        raise ValueError(f"Form '{form_id}' contains no questions.")

    first_question = state.current_question
    opening = first_question.conversational_hint or first_question.text

    # Add the opening message to the transcript as the assistant's first turn
    state.transcript.append(TranscriptMessage(role="assistant", content=opening))

    return session_id, opening, state.total_questions


async def process_response(session_id: str, patient_answer: str) -> InterviewTurn:
    """
    Process a patient's answer and return the next InterviewTurn.

    Raises KeyError if session_id is unknown.
    Raises ValueError if the session is already complete.
    """
    state = _SESSIONS.get(session_id)
    if state is None:
        raise KeyError(f"Session '{session_id}' not found.")
    if state.status != "in_progress":
        raise ValueError(f"Session '{session_id}' is already {state.status}.")

    # Keyword emergency check before LLM
    emergency_phrase = _keyword_triage_check(patient_answer)
    if emergency_phrase:
        state.triage_flags.append(emergency_phrase)

    # Add patient input to transcript
    state.transcript.append(
        TranscriptMessage(role="user", content=patient_answer)
    )

    # LLM call
    turn = await _call_llm(state)

    # Propagate emergency flag from keyword check
    if emergency_phrase:
        turn = InterviewTurn(
            ai_response=turn.ai_response,
            question_answered_id=turn.question_answered_id,
            extracted_value=turn.extracted_value,
            next_question_id=turn.next_question_id,
            triage_flag=True,
            triage_reason=emergency_phrase,
            form_complete=turn.form_complete,
        )

    # Persist extracted answer
    if turn.question_answered_id and turn.extracted_value is not None:
        state.answers[turn.question_answered_id] = turn.extracted_value

    # Persist LLM triage flag
    if turn.triage_flag and turn.triage_reason:
        if turn.triage_reason not in state.triage_flags:
            state.triage_flags.append(turn.triage_reason)

    # Add AI response to transcript
    state.transcript.append(
        TranscriptMessage(role="assistant", content=turn.ai_response)
    )

    # Advance position — respect next_question_id hint from LLM if valid
    if turn.next_question_id and turn.next_question_id in state.question_index_map:
        state.current_question_index = state.question_index_map[turn.next_question_id]
    else:
        state.advance_to_next()

    if turn.form_complete or state.current_question is None:
        state.status = "completed"

    return turn


def get_transcript(session_id: str) -> list[TranscriptMessage]:
    """Return a copy of the raw transcript for a session."""
    state = _SESSIONS.get(session_id)
    if state is None:
        raise KeyError(f"Session '{session_id}' not found.")
    return list(state.transcript)


async def get_summary(session_id: str) -> SessionSummary:
    """
    Build and return a structured triage summary for a session.
    Can be called any time — does not require the session to be complete.
    """
    state = _SESSIONS.get(session_id)
    if state is None:
        raise KeyError(f"Session '{session_id}' not found.")

    triage_level = state.compute_triage_level()
    scores = {
        section.id: state.compute_section_score(section.id)
        for section in state.form.sections
        if state.form.scoring.enabled
    }

    # Derive chief complaint from the first free_text answer if available
    chief_complaint = ""
    for q in state.all_questions:
        if q.type == "free_text":
            val = state.answers.get(q.id)
            if isinstance(val, str) and val.strip():
                chief_complaint = val.strip()
                break

    routing_map: dict[TriageLevel, str] = {
        "emergency": "Escalate to emergency evaluation immediately.",
        "high":      "Offer same-day urgent care or clinician callback.",
        "moderate":  "Offer next-available primary care or telehealth intake.",
        "low":       "Offer routine visit options and self-care follow-up guidance.",
    }

    return SessionSummary(
        session_id=session_id,
        form_id=state.form.form_id,
        status=state.status,
        answers=state.answers,
        triage_level=triage_level,
        triage_flags=state.triage_flags,
        scores=scores,
        chief_complaint=chief_complaint,
        recommended_routing=routing_map.get(triage_level, ""),
        notes=(
            f"Completed {state.questions_answered()} of {state.total_questions} questions. "
            f"Form: {state.form.title}."
        ),
    )
