# app/routes/patient_checkin.py
# Patient Self Check-In / Kiosk routes.
#
# Used by the Patient Check-In Portal (kiosk or patient device).
# No authentication required — identity is verified by name + DOB + visit date.
#
# Workflow:
#   1. Kiosk validates patient:      POST /patient/validate
#   2. Kiosk loads prefilled forms:  GET  /patient/checkin/{visit_id}/forms
#   3. Patient corrects/completes:   POST /patient/checkin/{visit_id}/submit
#   4. Patient signs consent:        POST /patient/checkin/{visit_id}/sign

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    CheckInField,
    CheckInFormGroup,
    CheckInFormsResponse,
    CheckInSignRequest,
    CheckInSignResponse,
    CheckInSubmitRequest,
    CheckInSubmitResponse,
    PatientValidateRequest,
    PatientValidateResponse,
)
from app.services import ai_engine, store

router = APIRouter()


@router.post("/validate", response_model=PatientValidateResponse)
def validate_patient(body: PatientValidateRequest):
    """
    Verify a patient's identity using name, date of birth, and appointment date.
    Returns the matching patient record and visit if found.

    The kiosk calls this first — no other data is exposed until identity is confirmed.
    """
    patient = store.find_patient_by_identity(
        first_name=body.first_name,
        last_name=body.last_name,
        dob=body.date_of_birth,
    )

    if not patient:
        return PatientValidateResponse(
            valid=False,
            message="No patient record matched the provided name and date of birth. "
                    "Please see a staff member for assistance.",
        )

    visit = store.find_visit_by_date(patient.patient_id, body.appointment_date)
    if not visit:
        return PatientValidateResponse(
            valid=False,
            patient=patient,
            message=f"No appointment found for {body.appointment_date}. "
                    "Please confirm your appointment date or speak with a staff member.",
        )

    if visit.status == "cancelled":
        return PatientValidateResponse(
            valid=False,
            patient=patient,
            visit=visit,
            message="This appointment has been cancelled. Please contact the clinic.",
        )

    return PatientValidateResponse(
        valid=True,
        patient=patient,
        visit=visit,
        message=f"Welcome, {patient.first_name}! Please review your information below.",
    )


@router.get("/checkin/{visit_id}/forms", response_model=CheckInFormsResponse)
def get_checkin_forms(visit_id: str):
    """
    Return all forms assigned to this visit with prefilled values highlighted.
    Fields are tagged as:
      - prefilled (source: ehr) — patient should review and confirm
      - missing — patient must fill in
    The kiosk uses this to build the review/complete interface.
    """
    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")

    assignments = store.get_assignments_for_visit(visit_id)
    if not assignments:
        raise HTTPException(
            status_code=404,
            detail=f"No forms assigned to visit {visit_id}.",
        )

    form_groups: List[CheckInFormGroup] = []
    total_missing = 0
    total_needs_confirmation = 0

    for assignment in assignments:
        template = store.get_template(assignment.template_id)
        if not template:
            continue

        # Get prefilled form from the ai_engine in-memory store (populated after /intake/prefill)
        prefilled = ai_engine.get_prefilled_form(assignment.assignment_id)
        filled_map: Dict[str, Any] = {}
        if prefilled:
            filled_map = {f.field_id: f for f in prefilled.filled_fields}

        fields: List[CheckInField] = []
        for field in template.fields:
            pf = filled_map.get(field.field_id)
            if pf:
                # EHR-prefilled: patient should confirm
                cf = CheckInField(
                    field_id=field.field_id,
                    label=field.label,
                    type=field.type,
                    section=field.section,
                    required=field.required,
                    prefilled_value=pf.value,
                    source=pf.source,
                    needs_confirmation=True,
                    is_missing=False,
                )
                total_needs_confirmation += 1
            else:
                # Missing: patient must fill in
                cf = CheckInField(
                    field_id=field.field_id,
                    label=field.label,
                    type=field.type,
                    section=field.section,
                    required=field.required,
                    prefilled_value=None,
                    source=None,
                    needs_confirmation=False,
                    is_missing=True,
                )
                if field.required:
                    total_missing += 1

        form_groups.append(CheckInFormGroup(
            assignment_id=assignment.assignment_id,
            form_name=template.name,
            fields=fields,
        ))

    return CheckInFormsResponse(
        visit_id=visit_id,
        patient_id=visit.patient_id,
        forms=form_groups,
        total_missing=total_missing,
        total_needs_confirmation=total_needs_confirmation,
    )


@router.post("/checkin/{visit_id}/submit", response_model=CheckInSubmitResponse)
def submit_checkin_answers(visit_id: str, body: CheckInSubmitRequest):
    """
    Save the patient's answers and any corrections to prefilled fields.
    This is called after the patient reviews and fills in their information on the kiosk.

    The patient's answers (field_id → value) are stored in-memory and merged with
    the EHR-prefilled data for the nurse's review.
    """
    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")

    if not body.answers:
        raise HTTPException(status_code=422, detail="No answers provided.")

    # Store kiosk answers into a session keyed by visit_id for nurse review
    session_key = f"kiosk-{visit_id}"
    existing = store.get_session(session_key)
    from app.models.schemas import IntakeCallSession
    if not existing:
        session = IntakeCallSession(
            session_id=session_key,
            session_type="intake",
            visit_id=visit_id,
            patient_id=visit.patient_id,
            status="in_progress",
            collected_answers=body.answers,
            created_at=store.now_iso(),
        )
        store.save_session(session)
    else:
        merged = {**existing.collected_answers, **body.answers}
        store.update_session(session_key, {"collected_answers": merged})

    return CheckInSubmitResponse(
        visit_id=visit_id,
        saved_fields=len(body.answers),
        message=f"Saved {len(body.answers)} field(s). Please proceed to sign consent.",
    )


@router.post("/checkin/{visit_id}/sign", response_model=CheckInSignResponse)
def sign_consent(visit_id: str, body: CheckInSignRequest):
    """
    Record the patient's consent signature and mark the visit as checked in.
    Signature is stored as the patient's typed name or "ACCEPTED".
    """
    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")

    if not body.signature or not body.signature.strip():
        raise HTTPException(status_code=422, detail="Signature cannot be empty.")

    # Store signature in the kiosk session
    session_key = f"kiosk-{visit_id}"
    store.update_session(session_key, {
        "collected_answers": {
            **(store.get_session(session_key).collected_answers if store.get_session(session_key) else {}),
            "consent_signature": body.signature.strip(),
            "consent_date": body.signed_at,
        },
        "status": "completed",
        "completed_at": store.now_iso(),
    })

    # Update visit status to checked_in
    store.update_visit_status(visit_id, "checked_in")

    patient = store.get_patient(visit.patient_id)
    patient_name = patient.full_name if patient else "Patient"

    return CheckInSignResponse(
        visit_id=visit_id,
        signed=True,
        message=f"Thank you, {patient_name}. Your check-in is complete. Please have a seat — a staff member will call you shortly.",
    )
