# app/routes/followups.py
# Post-discharge follow-up routes — used by the Staff Portal.
#
# Workflow:
#   1. Staff browses question bank:   GET  /followups/question-bank
#   2. Staff schedules follow-up:     POST /followups/schedule
#   3. Follow-up call happens via:    POST /interview/start (session_type=followup)
#   4. Staff reviews results:         GET  /followups/{task_id}

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    FollowUpQuestion,
    FollowUpResponse,
    PostDischargeFollowUpTask,
    ScheduleFollowUpRequest,
)
from app.services import store

router = APIRouter()


# ── Question bank ─────────────────────────────────────────────────────────────

@router.get("/question-bank", response_model=List[FollowUpQuestion])
def get_question_bank():
    """
    Return all standard follow-up questions available to doctors.
    Staff Portal shows these for selection when building a follow-up call.
    """
    return store.get_question_bank()


# ── Follow-up tasks ───────────────────────────────────────────────────────────

@router.get("", response_model=List[PostDischargeFollowUpTask])
def list_followup_tasks(patient_id: Optional[str] = Query(default=None)):
    """
    Return all scheduled follow-up tasks.
    Optionally filter by patient_id.
    """
    return store.get_all_followup_tasks(patient_id=patient_id)


@router.get("/{task_id}", response_model=PostDischargeFollowUpTask)
def get_followup_task(task_id: str):
    """Return a single follow-up task with its current status and flags."""
    task = store.get_followup_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Follow-up task {task_id} not found.")
    return task


@router.post("/schedule", response_model=PostDischargeFollowUpTask)
def schedule_followup(body: ScheduleFollowUpRequest):
    """
    Schedule a post-discharge follow-up call for a patient.
    Staff selects question bank questions and optionally adds custom questions.
    """
    patient = store.get_patient(body.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {body.patient_id} not found.")

    visit = store.get_visit(body.visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {body.visit_id} not found.")

    # Resolve question bank selections
    questions: List[FollowUpQuestion] = []
    for qid in body.question_bank_ids:
        q = store.get_question(qid)
        if q:
            questions.append(q)
        else:
            raise HTTPException(status_code=404, detail=f"Question bank item {qid} not found.")

    # Add custom questions
    for i, custom_text in enumerate(body.custom_questions):
        if custom_text.strip():
            questions.append(FollowUpQuestion(
                question_id=f"custom-{store.new_id()}",
                text=custom_text.strip(),
                category="custom",
                is_custom=True,
            ))

    if not questions:
        raise HTTPException(
            status_code=422,
            detail="At least one question is required. Add question bank IDs or custom questions.",
        )

    task = PostDischargeFollowUpTask(
        task_id=store.new_id("task-"),
        patient_id=body.patient_id,
        visit_id=body.visit_id,
        created_by=body.created_by,
        scheduled_at=body.scheduled_at,
        status="scheduled",
        questions=questions,
        created_at=store.now_iso(),
    )
    return store.create_followup_task(task)


@router.get("/{task_id}/responses", response_model=List[FollowUpResponse])
def get_followup_responses(task_id: str):
    """Return all responses collected during a completed follow-up call."""
    task = store.get_followup_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Follow-up task {task_id} not found.")
    return store.get_responses_for_task(task_id)
