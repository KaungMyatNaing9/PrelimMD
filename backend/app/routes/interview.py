# app/routes/interview.py
# Session orchestration routes — used by both portals and the voice agent.
#
# Supports two session types:
#   "intake"   — collects missing fields before a patient visit
#   "followup" — post-discharge check-in driven by a doctor-configured question list
#
# Typical intake flow:
#   POST /interview/start      → create session, get opening greeting
#   POST /interview/answer     → send patient answer, get next question
#   POST /interview/complete   → close session (or happens automatically when done)
#   GET  /interview/session/{id} → review full session (staff portal)

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    AnswerRequest,
    AnswerResponse,
    FormSchema,
    IntakeCallSession,
    MissingField,
    StartSessionRequest,
)
from app.services import ai_engine, interview_engine, store

PHONE_BLOCKLIST = {
    "ssn",
    "social_security",
    "patient_signature",
    "signature",
    "consent_signature",
    "consent_date",
}

router = APIRouter()


@router.post("/start", response_model=IntakeCallSession)
def start_session(body: StartSessionRequest):
    """
    Create a new interview session.

    For intake:
      - visit_id must be provided
      - The visit must have at least one assigned form that has been prefilled
      - Returns the session with the opening greeting as the first AI turn

    For followup:
      - task_id must be provided
      - The follow-up task must exist and be in "scheduled" status
      - Returns the session with the opening greeting
    """
    if body.session_type == "intake":
        if not body.visit_id:
            raise HTTPException(status_code=422, detail="visit_id is required for intake sessions.")

        visit = store.get_visit(body.visit_id)
        if not visit:
            raise HTTPException(status_code=404, detail=f"Visit {body.visit_id} not found.")

        # Collect all missing fields across assigned forms for this visit
        assignments = store.get_assignments_for_visit(body.visit_id)
        if not assignments:
            raise HTTPException(
                status_code=404,
                detail=f"No forms assigned to visit {body.visit_id}. "
                       "Assign forms and run POST /intake/prefill/{visit_id} first.",
            )

        all_missing: list[MissingField] = []
        for assignment in assignments:
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
            if prefilled:
                all_missing.extend(
                    [field for field in prefilled.missing_fields if field.field_id not in PHONE_BLOCKLIST]
                )

        if not all_missing:
            # No missing fields — nothing to collect; create a trivial completed session
            session = interview_engine.start_intake_session(
                visit_id=body.visit_id,
                patient_id=visit.patient_id,
                missing_fields=[],
            )
            store.update_session(session.session_id, {"status": "completed"})
            return store.get_session(session.session_id)

        return interview_engine.start_intake_session(
            visit_id=body.visit_id,
            patient_id=visit.patient_id,
            missing_fields=all_missing,
        )

    elif body.session_type == "followup":
        if not body.task_id:
            raise HTTPException(status_code=422, detail="task_id is required for followup sessions.")

        task = store.get_followup_task(body.task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Follow-up task {body.task_id} not found.")

        if task.status not in ("scheduled", "in_progress"):
            raise HTTPException(
                status_code=409,
                detail=f"Follow-up task is already {task.status}.",
            )

        return interview_engine.start_followup_session(body.task_id)

    else:
        raise HTTPException(status_code=422, detail=f"Unknown session_type: {body.session_type}")


@router.post("/answer", response_model=AnswerResponse)
def submit_answer(body: AnswerRequest):
    """
    Submit a patient's answer and get the next question.

    Call this in a loop until is_done=true. Each call:
      - Stores the patient's answer in the session
      - Runs the AI to decide the next question (or signals completion)
      - Checks for concerning keywords (follow-up sessions)
      - Returns the next question text and any flags

    When is_done=true, call POST /interview/complete to close the session.
    """
    session = store.get_session(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {body.session_id} not found.")

    if session.status != "in_progress":
        raise HTTPException(
            status_code=409,
            detail=f"Session is already {session.status}. Cannot submit more answers.",
        )

    if not body.answer or not body.answer.strip():
        raise HTTPException(status_code=422, detail="Answer cannot be empty.")

    if session.session_type == "intake":
        return interview_engine.process_intake_answer(body.session_id, body.answer.strip())
    elif session.session_type == "followup":
        return interview_engine.process_followup_answer(body.session_id, body.answer.strip())
    else:
        raise HTTPException(status_code=500, detail=f"Unknown session type: {session.session_type}")


@router.get("/session/{session_id}", response_model=IntakeCallSession)
def get_session(session_id: str):
    """
    Return the full session including all conversation turns, collected answers, and flags.
    Staff Portal uses this to review what was collected during the call.
    """
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return session


@router.post("/complete")
def complete_session(session_id: str):
    """
    Explicitly close a session as complete.
    Use this when the call ends naturally or when the patient needs to hang up.
    Sessions also auto-complete when all questions are answered via POST /interview/answer.
    """
    session = interview_engine.complete_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return {"session_id": session_id, "status": session.status, "message": "Session marked complete."}
