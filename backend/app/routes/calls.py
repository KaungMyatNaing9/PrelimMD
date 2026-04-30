# app/routes/calls.py
# Routes for the call question/response flow between Person 2 and Person 3.
# Owner: AI (Person 2) — interface for Communication agent (Person 3)

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    CallResponses, CompletedForm,
    NextQuestionRequest, NextQuestionResponse,
    OpeningQuestion, QuestionsPayload,
)
from app.services import ai_engine

router = APIRouter()


@router.get("/{call_id}/questions", response_model=QuestionsPayload)
def get_questions(
    call_id: str,
    form_id: str,
    patient_name: str = "Patient",
    max_questions: int = 7,
    reason_for_visit: str = "",
):
    """
    Return compound questions for a pre-visit call.
    Person 3 calls this to get what to ask the patient.

    form_id:          the form_id returned from POST /forms/upload + /prefill
    max_questions:    max number of compound questions (default 7 ≈ ~2 min call).
                      Required questions are always included first.
    reason_for_visit: if Person 3 has already asked the opening question and
                      captured the patient's answer, pass it here so we can
                      filter out questions whose answers were already given.
    """
    prefilled = ai_engine.get_prefilled_form(form_id)
    if not prefilled:
        raise HTTPException(
            status_code=404,
            detail=f"No prefilled form found for form_id={form_id}. "
                   "Run POST /forms/{form_id}/prefill first."
        )

    opening = [
        OpeningQuestion(
            question_id="open_0",
            question="Hi, can I get your full name and date of birth to confirm I have the right person?",
            purpose="identity_verification",
        ),
        OpeningQuestion(
            question_id="open_1",
            question="And what's the reason for your visit today?",
            purpose="reason_for_visit",
        ),
    ]

    questions = ai_engine.get_call_questions(form_id, reason_for_visit.strip())
    required  = [q for q in questions if q.required]
    optional  = [q for q in questions if not q.required]
    slots_for_optional = max(0, max_questions - len(required))
    selected = required + optional[:slots_for_optional]

    # 17s per form question + 20s for the 2 opening questions
    estimated_minutes = max(1, round((len(selected) * 17 + 40) / 60))

    return QuestionsPayload(
        call_id=call_id,
        patient_name=patient_name,
        opening=opening,
        questions=selected,
        estimated_minutes=estimated_minutes,
    )


@router.post("/{call_id}/next-question", response_model=NextQuestionResponse)
def next_question(call_id: str, body: NextQuestionRequest):  # noqa: ARG001
    """
    Adaptive turn-by-turn question generation.
    Person 3 calls this after each patient answer to get the next question.

    Pass the full conversation so far (opening + all prior exchanges).
    Returns the next question to ask, or done=true when all required fields
    are covered. The agent reads what has already been said and will not
    repeat information the patient already volunteered.

    Loop until done=true, then call POST /{call_id}/responses to finalize.
    """
    result = ai_engine.get_next_question(body.form_id, [t.model_dump() for t in body.conversation])
    return NextQuestionResponse(
        question=result.get("question"),
        field_ids=result.get("field_ids", []),
        done=result.get("done", False),
    )


@router.post("/{call_id}/responses", response_model=CompletedForm)
def submit_responses(call_id: str, form_id: str, responses: CallResponses):
    """
    Submit collected patient answers and finalize the form.
    Person 3 calls this after the voice session completes.
    """
    try:
        return ai_engine.finalize_form(form_id, responses)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Form filler failed: {exc}")
