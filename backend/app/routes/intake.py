# app/routes/intake.py
# Staff-side intake workflow routes.
#
# Workflow:
#   1. Staff assigns a form to a visit via POST /intake/assign
#   2. Staff triggers prefill:      POST /intake/prefill/{visit_id}
#   3. Staff reviews readiness:    GET  /intake/overview/{visit_id}
#   4. Staff schedules a call:     POST /intake/schedule-call
#   5. Session starts via:         POST /interview/start or /voice/intake/start
#   6. Staff reviews session:      GET  /intake/session/{session_id}

from typing import Optional

from fastapi import APIRouter, Body, HTTPException

from app.models.schemas import (
    AssignedForm,
    AssignFormRequest,
    FormSchema,
    FormTemplate,
    IntakeCallScheduleResponse,
    IntakeCallSession,
    IntakeFormOverview,
    IntakeOverviewResponse,
    MissingField,
)
from app.services import ai_engine, interview_engine, store

router = APIRouter()

PHONE_BLOCKLIST = {
    "ssn",
    "social_security",
    "patient_signature",
    "signature",
    "consent_signature",
    "consent_date",
}


def _assignment_schema(assignment: AssignedForm, template: FormTemplate) -> FormSchema:
    return FormSchema(
        form_id=assignment.form_id or assignment.assignment_id,
        form_name=template.name,
        fields=template.fields,
    )


def _prefilled_for_assignment(assignment: AssignedForm, patient_id: str, template: FormTemplate):
    schema = _assignment_schema(assignment, template)
    prefilled = ai_engine.get_prefilled_form(schema.form_id)
    if prefilled:
        return prefilled
    return ai_engine.local_prefill(schema, patient_id)


def _call_safe_missing_fields(prefilled) -> list[MissingField]:
    return [field for field in prefilled.missing_fields if field.field_id not in PHONE_BLOCKLIST]


def _build_overview(visit_id: str) -> IntakeOverviewResponse:
    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")

    assignments = store.get_assignments_for_visit(visit_id)
    if not assignments:
        raise HTTPException(
            status_code=404,
            detail=f"No forms assigned to visit {visit_id}. Use POST /intake/assign first.",
        )

    forms: list[IntakeFormOverview] = []
    total_fields = 0
    filled_fields = 0
    remaining_fields = 0
    call_remaining_fields = 0

    for assignment in assignments:
        template = store.get_template(assignment.template_id)
        if not template:
            continue

        prefilled = _prefilled_for_assignment(assignment, visit.patient_id, template)
        call_missing = _call_safe_missing_fields(prefilled)
        completion_percent = int((prefilled.stats.filled / prefilled.stats.total) * 100) if prefilled.stats.total else 100

        total_fields += prefilled.stats.total
        filled_fields += prefilled.stats.filled
        remaining_fields += prefilled.stats.missing
        call_remaining_fields += len(call_missing)

        forms.append(
            IntakeFormOverview(
                assignment_id=assignment.assignment_id,
                template_id=assignment.template_id,
                form_name=template.name,
                status=assignment.status,
                total_fields=prefilled.stats.total,
                filled_fields=prefilled.stats.filled,
                remaining_fields=prefilled.stats.missing,
                call_remaining_fields=len(call_missing),
                completion_percent=completion_percent,
                remaining_field_labels=[field.label for field in prefilled.missing_fields],
                call_questions=[field.question for field in call_missing],
            )
        )

    overall_completion = int((filled_fields / total_fields) * 100) if total_fields else 100
    return IntakeOverviewResponse(
        visit_id=visit_id,
        patient_id=visit.patient_id,
        total_forms=len(forms),
        total_fields=total_fields,
        filled_fields=filled_fields,
        remaining_fields=remaining_fields,
        call_remaining_fields=call_remaining_fields,
        completion_percent=overall_completion,
        forms=forms,
    )


def _missing_fields_for_visit(visit_id: str) -> list[MissingField]:
    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")

    missing_fields: list[MissingField] = []
    for assignment in store.get_assignments_for_visit(visit_id):
        template = store.get_template(assignment.template_id)
        if not template:
            continue
        prefilled = _prefilled_for_assignment(assignment, visit.patient_id, template)
        missing_fields.extend(_call_safe_missing_fields(prefilled))
    return missing_fields


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


@router.post("/prefill/{visit_id}", response_model=list)
def prefill_visit_forms(visit_id: str):
    """
    For each form assigned to this visit, run the EHR diff agent and prefill known fields.
    Returns a list of PrefilledForm objects (one per assigned form).

    Staff Portal calls this after assigning forms. The prefill runs automatically
    from the mock EHR data - no patient interaction required at this step.
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

        form_schema = _assignment_schema(assignment, template)

        try:
            prefilled = ai_engine.retrieve_and_diff(form_schema, visit.patient_id)
        except Exception:
            prefilled = ai_engine.local_prefill(form_schema, visit.patient_id)

        store.update_assignment(
            assignment.assignment_id,
            {
                "form_id": form_schema.form_id,
                "status": "prefilled",
            },
        )
        results.append(prefilled)

    return results


@router.get("/overview/{visit_id}", response_model=IntakeOverviewResponse)
def get_intake_overview(visit_id: str):
    """
    Return a staff-friendly summary of intake readiness for this visit.
    Includes per-form completion, remaining fields, and voice-call prompts.
    """
    return _build_overview(visit_id)


@router.post("/schedule-call", response_model=IntakeCallScheduleResponse)
def schedule_intake_call(
    visit_id: str = Body(...),
    scheduled_at: Optional[str] = Body(default=None),
):
    """
    Record that an intake call has been scheduled and create the intake session payload
    the voice layer can use to ask the remaining call-safe questions.
    """
    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")

    overview = _build_overview(visit_id)
    missing_fields = _missing_fields_for_visit(visit_id)
    session = interview_engine.start_intake_session(
        visit_id=visit_id,
        patient_id=visit.patient_id,
        missing_fields=missing_fields,
    )

    if missing_fields:
        for assignment in store.get_assignments_for_visit(visit_id):
            if assignment.status in ("assigned", "prefilled"):
                store.update_assignment(assignment.assignment_id, {"status": "in_call"})
    else:
        store.update_session(
            session.session_id,
            {
                "status": "completed",
                "completed_at": store.now_iso(),
            },
        )

    patient = store.get_patient(visit.patient_id)
    call_time = scheduled_at or store.now_iso()
    note = (
        "Intake call scheduled. Launch the returned voice flow or hand the session to Twilio."
        if overview.call_remaining_fields
        else "No call-safe fields are remaining. The patient can be sent directly to kiosk review."
    )

    return IntakeCallScheduleResponse(
        visit_id=visit_id,
        session_id=session.session_id,
        scheduled_at=call_time,
        status="scheduled",
        remaining_fields=overview.remaining_fields,
        call_remaining_fields=overview.call_remaining_fields,
        patient_phone=patient.phone if patient else None,
        voice_start_path=f"/voice/intake/start?session_id={session.session_id}",
        note=note,
    )


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
