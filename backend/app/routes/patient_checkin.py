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
from fastapi import APIRouter, HTTPException, UploadFile
import re

from app.models.schemas import (
    AssignedForm,
    CheckInField,
    CheckInFormGroup,
    CheckInFormsResponse,
    CheckInScanResponse,
    CheckInScannedField,
    CheckInSignRequest,
    CheckInSignResponse,
    CheckInSubmitRequest,
    CheckInSubmitResponse,
    CompletedForm,
    CompletedFormField,
    FormSchema,
    NewPatientCheckInRequest,
    NewPatientCheckInResponse,
    PatientValidateRequest,
    PatientValidateResponse,
    PatientAllergy,
    PatientCondition,
    PatientMedication,
    Patient,
    ReusableFieldFact,
    ScheduledVisit,
)
from app.services import ai_engine, store

router = APIRouter()
SCAN_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "application/pdf"}

PATIENT_PROFILE_FIELDS = {
    "date_of_birth",
    "gender",
    "phone",
    "email",
    "address",
    "insurance_provider",
    "insurance_id",
    "emergency_contact_name",
    "emergency_contact_phone",
    "emergency_contact_relation",
}

REUSABLE_FIELDS = PATIENT_PROFILE_FIELDS | {
    "full_name",
    "current_medications",
    "known_allergies",
    "conditions",
}


def _split_list_value(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    text = str(value)
    parts = [item.strip(" .") for item in re.split(r"[\n,;]+", text) if item.strip()]
    return [part for part in parts if part]


def _save_reusable_facts(patient_id: str, answers: Dict[str, Any], confirmed_at: str):
    for key, value in answers.items():
        if key not in REUSABLE_FIELDS or value in (None, "", [], {}):
            continue
        store.save_reusable_field_fact(
            ReusableFieldFact(
                fact_id=f"fact-{patient_id}-{key}",
                patient_id=patient_id,
                field_key=key,
                value=str(value),
                source="patient_kiosk",
                confidence=100,
                last_confirmed_at=confirmed_at,
            )
        )


def _save_clinical_history(patient_id: str, answers: Dict[str, Any], confirmed_at: str):
    medication_items = _split_list_value(answers.get("current_medications"))
    medications = [
        PatientMedication(
            medication_id=f"med-{patient_id}-{index}",
            patient_id=patient_id,
            name=item,
            dosage=None,
            frequency=None,
            active=True,
            last_confirmed_at=confirmed_at,
        )
        for index, item in enumerate(medication_items, start=1)
    ]
    if "current_medications" in answers:
        store.replace_patient_medications(patient_id, medications)

    allergy_items = _split_list_value(answers.get("known_allergies"))
    allergies = [
        PatientAllergy(
            allergy_id=f"allergy-{patient_id}-{index}",
            patient_id=patient_id,
            substance=item,
            reaction=None,
            severity=None,
            active=True,
            last_confirmed_at=confirmed_at,
        )
        for index, item in enumerate(allergy_items, start=1)
    ]
    if "known_allergies" in answers:
        store.replace_patient_allergies(patient_id, allergies)

    condition_items = _split_list_value(answers.get("conditions"))
    conditions = [
        PatientCondition(
            condition_id=f"condition-{patient_id}-{index}",
            patient_id=patient_id,
            condition=item,
            status="active",
            onset=None,
            active=True,
            last_confirmed_at=confirmed_at,
        )
        for index, item in enumerate(condition_items, start=1)
    ]
    if "conditions" in answers:
        store.replace_patient_conditions(patient_id, conditions)


def _persist_patient_answers(visit_id: str, patient_id: str, answers: Dict[str, Any]):
    patient_updates = {
        key: value
        for key, value in answers.items()
        if key in PATIENT_PROFILE_FIELDS and value not in (None, "", [], {})
    }
    if patient_updates:
        store.update_patient(patient_id, patient_updates)

    reason_for_visit = answers.get("reason_for_visit")
    if reason_for_visit not in (None, "", [], {}):
        visit = store.get_visit(visit_id)
        if visit:
            store.create_visit(
                ScheduledVisit(
                    **{
                        **visit.model_dump(),
                        "reason": str(reason_for_visit).strip(),
                    }
                )
            )
    confirmed_at = answers.get("consent_date") or store.now_iso()
    _save_reusable_facts(patient_id, answers, str(confirmed_at))
    _save_clinical_history(patient_id, answers, str(confirmed_at))


def _save_completed_visit_forms(visit_id: str, patient_id: str, answers: Dict[str, Any]):
    assignments = store.get_assignments_for_visit(visit_id)
    for assignment in assignments:
        template = store.get_template(assignment.template_id)
        if not template:
            continue

        form_id = assignment.form_id or assignment.assignment_id
        prefilled = ai_engine.get_prefilled_form(form_id)
        if not prefilled:
            prefilled = ai_engine.prefill_from_db(
                FormSchema(
                    form_id=form_id,
                    form_name=template.name,
                    fields=template.fields,
                ),
                patient_id,
                visit_id=visit_id,
            )

        allowed_fields = {field.field_id for field in template.fields}
        merged: dict[str, CompletedFormField] = {
            field.field_id: CompletedFormField(
                field_id=field.field_id,
                value=field.value,
                source=field.source,
                needs_review=field.needs_review,
            )
            for field in prefilled.filled_fields
        }

        for key, value in answers.items():
            if key not in allowed_fields or value in (None, "", [], {}):
                continue
            merged[key] = CompletedFormField(
                field_id=key,
                value=value,
                source="patient_kiosk",
                needs_review=False,
            )

        completed = CompletedForm(
            form_id=form_id,
            patient_id=patient_id,
            visit_id=visit_id,
            template_id=assignment.template_id,
            fields=list(merged.values()),
            created_at=store.now_iso(),
        )
        store.save_completed_form(completed)
        store.update_assignment(assignment.assignment_id, {"status": "signed"})


@router.post("/new-checkin", response_model=NewPatientCheckInResponse)
def create_new_patient_checkin(body: NewPatientCheckInRequest):
    """
    Create a lightweight patient shell plus today's visit for first-time patients.
    A default intake form is attached immediately so the kiosk can continue into review.
    """
    template = store.get_template(body.template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {body.template_id} not found.")

    patient = Patient(
        patient_id=store.new_id("patient-"),
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        date_of_birth=body.date_of_birth,
        gender=body.gender,
        phone=body.phone.strip(),
        email=body.email.strip() if body.email else None,
        address=body.address.strip() if body.address else None,
        insurance_provider=body.insurance_provider.strip() if body.insurance_provider else None,
        insurance_id=body.insurance_id.strip() if body.insurance_id else None,
        emergency_contact_name=body.emergency_contact_name.strip() if body.emergency_contact_name else None,
        emergency_contact_phone=body.emergency_contact_phone.strip() if body.emergency_contact_phone else None,
        emergency_contact_relation=body.emergency_contact_relation.strip() if body.emergency_contact_relation else None,
    )
    store.create_patient(patient)

    visit = ScheduledVisit(
        visit_id=store.new_id("visit-"),
        patient_id=patient.patient_id,
        visit_date=body.appointment_date,
        visit_time=body.appointment_time,
        provider_name=body.provider_name,
        department=body.department,
        reason=body.reason_for_visit,
        status="scheduled",
        notes="Created from first-time patient kiosk check-in.",
    )
    store.create_visit(visit)

    assignment = AssignedForm(
        assignment_id=store.new_id("assign-"),
        visit_id=visit.visit_id,
        template_id=template.template_id,
        form_id=store.new_id("form-"),
        assigned_by=body.assigned_by,
        assigned_at=store.now_iso(),
        status="prefilled",
    )
    store.create_assignment(assignment)

    ai_engine.local_prefill(
        FormSchema(
            form_id=assignment.form_id,
            form_name=template.name,
            fields=template.fields,
        ),
        patient.patient_id,
        visit_id=visit.visit_id,
    )

    return NewPatientCheckInResponse(
        patient=patient,
        visit=visit,
        assignment_id=assignment.assignment_id,
        message="New patient profile created. Please continue with form review and consent.",
    )


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

        # Prefer the assigned form_id, then fall back to assignment_id for older records.
        prefilled = ai_engine.get_prefilled_form(assignment.form_id or assignment.assignment_id)
        if not prefilled:
            prefilled = ai_engine.local_prefill(
                FormSchema(
                    form_id=assignment.form_id or assignment.assignment_id,
                    form_name=template.name,
                    fields=template.fields,
                ),
                visit.patient_id,
                visit_id=visit.visit_id,
            )
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
                    last_confirmed_at=pf.last_confirmed_at,
                    needs_confirmation=True,
                    is_stale=pf.is_stale,
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
                    last_confirmed_at=None,
                    needs_confirmation=False,
                    is_missing=True,
                )
                if field.required:
                    total_missing += 1
            fields.append(cf)

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


@router.post("/checkin/{visit_id}/scan", response_model=CheckInScanResponse)
async def scan_checkin_form(visit_id: str, file: UploadFile):
    """
    Accept a camera-captured image and map OCR'd values onto the visit's assigned intake forms.
    The patient still reviews everything before submission.
    """
    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")

    assignments = store.get_assignments_for_visit(visit_id)
    if not assignments:
        raise HTTPException(status_code=404, detail=f"No forms assigned to visit {visit_id}.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No image provided.")

    # Infer MIME from filename when the browser strips it (common on mobile WebKit).
    _EXT_MIME = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".heic": "image/heic",
        ".heif": "image/heif",
        ".pdf": "application/pdf",
    }
    content_type = file.content_type or ""
    if not content_type or content_type == "application/octet-stream":
        import os
        ext = os.path.splitext(file.filename or "")[1].lower()
        content_type = _EXT_MIME.get(ext, "")

    if content_type not in SCAN_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Please upload a JPG, PNG, WEBP image or a PDF.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    try:
        if content_type == "application/pdf":
            ocr_text = ai_engine.ocr_pdf_to_text(content)
        else:
            ocr_text = ai_engine.ocr_image_to_text(content, content_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Camera scan OCR failed: {exc}")

    if not ocr_text or not ocr_text.strip():
        return CheckInScanResponse(
            visit_id=visit_id,
            scanned_fields=[],
            applied_count=0,
            ocr_preview=None,
            message="No text could be read from the image. You can still fill in fields manually.",
        )

    merged_candidates: dict[str, CheckInScannedField] = {}
    for assignment in assignments:
        template = store.get_template(assignment.template_id)
        if not template:
            continue

        form_schema = FormSchema(
            form_id=assignment.form_id or assignment.assignment_id,
            form_name=template.name,
            fields=template.fields,
        )
        for candidate in ai_engine.extract_scanned_fields(form_schema, ocr_text):
            existing = merged_candidates.get(candidate.field_id)
            if not existing or candidate.confidence > existing.confidence:
                merged_candidates[candidate.field_id] = candidate

    scanned_fields = sorted(merged_candidates.values(), key=lambda field: (-field.confidence, field.label))
    preview = ocr_text[:500] if ocr_text else None

    return CheckInScanResponse(
        visit_id=visit_id,
        scanned_fields=scanned_fields,
        applied_count=len(scanned_fields),
        ocr_preview=preview,
        message=(
            f"Found {len(scanned_fields)} candidate field(s) from the camera scan. "
            "Please review and edit anything that looks off."
        ),
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
    _persist_patient_answers(visit_id, visit.patient_id, body.answers)

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
    _persist_patient_answers(
        visit_id,
        visit.patient_id,
        {
            **(store.get_session(session_key).collected_answers if store.get_session(session_key) else {}),
            "consent_signature": body.signature.strip(),
            "consent_date": body.signed_at,
        },
    )
    _save_completed_visit_forms(
        visit_id,
        visit.patient_id,
        {
            **(store.get_session(session_key).collected_answers if store.get_session(session_key) else {}),
            "consent_signature": body.signature.strip(),
            "consent_date": body.signed_at,
        },
    )

    # Update visit status to checked_in
    store.update_visit_status(visit_id, "checked_in")

    patient = store.get_patient(visit.patient_id)
    patient_name = f"{patient.first_name} {patient.last_name}" if patient else "Patient"

    return CheckInSignResponse(
        visit_id=visit_id,
        signed=True,
        message=f"Thank you, {patient_name}. Your check-in is complete. Please have a seat — a staff member will call you shortly.",
    )
