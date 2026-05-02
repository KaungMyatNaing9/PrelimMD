# app/routes/intake.py
# Staff-side intake workflow routes.
#
# Workflow:
#   1. Staff assigns a form to a visit via POST /forms/assign
#   2. Staff triggers prefill:      POST /intake/prefill/{visit_id}
#   3. Staff schedules a call:      POST /intake/schedule-call
#   4. Session starts via:          POST /interview/start
#   5. Staff reviews session:       GET  /intake/session/{session_id}

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, HTTPException

from app.models.schemas import (
    AssignedForm,
    AssignFormRequest,
    FormTemplate,
    IntakeCallSession,
    PrefilledForm,
)
from app.services import ai_engine, store

router = APIRouter()


# ── Assign a form template to a visit ────────────────────────────────────────

@router.get("/templates", response_model=list)
def list_form_templates():
    """Return all available form templates for staff to choose from."""
    return store.get_all_templates()


@router.post("/assign", response_model=AssignedForm)
def assign_form(body: AssignFormRequest):
    """
    Assign a form template to a patient visit.
    Staff Portal calls this when selecting which forms a patient needs to complete.
    """
    visit = store.get_visit(body.visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {body.visit_id} not found.")

    template = store.get_template(body.template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {body.template_id} not found.")

    assignment = AssignedForm(
        assignment_id=store.new_id("assign-"),
        visit_id=body.visit_id,
        template_id=body.template_id,
        assigned_by=body.assigned_by,
        assigned_at=store.now_iso(),
        status="assigned",
    )
    return store.create_assignment(assignment)


# ── Trigger EHR prefill for all forms assigned to a visit ────────────────────

@router.post("/prefill/{visit_id}", response_model=list)
def prefill_visit_forms(visit_id: str):
    """
    For each form assigned to this visit, run the EHR diff agent and prefill known fields.
    Returns a list of PrefilledForm objects (one per assigned form).

    Staff Portal calls this after assigning forms. The prefill runs automatically
    from the mock EHR data — no patient interaction required at this step.
    """
    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")

    assignments = store.get_assignments_for_visit(visit_id)
    if not assignments:
        raise HTTPException(
            status_code=404,
            detail=f"No forms assigned to visit {visit_id}. Use POST /intake/assign first.",
        )

    results = []
    for assignment in assignments:
        template = store.get_template(assignment.template_id)
        if not template:
            continue

        # Build a FormSchema from the template and run the prefill agent
        from app.models.schemas import FormSchema
        form_schema = FormSchema(
            form_id=assignment.assignment_id,  # use assignment_id as the form_id key
            form_name=template.name,
            fields=template.fields,
        )

        try:
            prefilled = ai_engine.retrieve_and_diff(form_schema, visit.patient_id)
            store.update_assignment(assignment.assignment_id, {
                "form_id": form_schema.form_id,
                "status": "prefilled",
            })
            results.append(prefilled)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Prefill failed for {assignment.assignment_id}: {exc}")

    return results


# ── Schedule an intake call ───────────────────────────────────────────────────

@router.post("/schedule-call")
def schedule_intake_call(
    visit_id: str = Body(...),
    scheduled_at: Optional[str] = Body(default=None),
):
    """
    Record that an intake call has been scheduled for this visit.
    Actual call initiation (Twilio/ElevenLabs outbound dial) is out of scope for MVP.

    Staff Portal calls this after prefill to mark the visit as "call scheduled".
    Returns the scheduled_at time and a note that the call system will handle dialing.
    """
    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")

    call_time = scheduled_at or store.now_iso()

    return {
        "visit_id": visit_id,
        "scheduled_at": call_time,
        "status": "scheduled",
        "note": "Intake call recorded. Outbound dialing is handled by the telephony layer (Twilio/ElevenLabs).",
    }


# ── Retrieve a session by ID ──────────────────────────────────────────────────

@router.get("/session/{session_id}", response_model=IntakeCallSession)
def get_intake_session(session_id: str):
    """
    Return the full intake call session including conversation turns and collected answers.
    Staff Portal uses this to review what was collected during the call.
    """
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return session
