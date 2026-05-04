import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.db_models import (
    AssignedFormRecord,
    CompletedFormRecord,
    FollowUpResponseRecord,
    FollowUpTaskRecord,
    FormTemplateRecord,
    InterviewSessionRecord,
    PatientAllergyRecord,
    PatientConditionRecord,
    PatientMedicationRecord,
    PatientRecord,
    QuestionBankRecord,
    ReusableFieldFactRecord,
    StaffUserRecord,
    VisitRecord,
    VoiceCallSessionRecord,
)
from app.models.schemas import (
    AssignedForm,
    CompletedForm,
    CompletedFormField,
    FollowUpQuestion,
    FollowUpResponse,
    FormField,
    FormTemplate,
    IntakeCallSession,
    Patient,
    PatientAllergy,
    PatientCondition,
    PatientMedication,
    PostDischargeFollowUpTask,
    ReusableFieldFact,
    ScheduledVisit,
    StaffUser,
    VoiceCallSession,
)
from app.services.seed_data import ASSIGNED_FORMS as _SEED_FORMS
from app.services.seed_data import FOLLOWUP_TASKS as _SEED_TASKS
from app.services.seed_data import PATIENTS as _SEED_PATIENTS
from app.services.seed_data import STAFF as _SEED_STAFF
from app.services.seed_data import VISITS as _SEED_VISITS

T = TypeVar("T", bound=BaseModel)

_INIT_LOCK = Lock()
_INITIALIZED = False


_TEMPLATES: Dict[str, FormTemplate] = {
    "template-001": FormTemplate(
        template_id="template-001",
        name="General Intake Form",
        description="Standard patient intake used for most visit types.",
        category="general_intake",
        fields=[
            FormField(field_id="full_name", label="Full Name", type="string", required=True, section="demographics", fhir_mapping="Patient.name"),
            FormField(field_id="date_of_birth", label="Date of Birth", type="date", required=True, section="demographics", fhir_mapping="Patient.birthDate"),
            FormField(field_id="gender", label="Gender", type="string", required=True, section="demographics", fhir_mapping="Patient.gender"),
            FormField(field_id="phone", label="Phone Number", type="phone", required=True, section="demographics", fhir_mapping="Patient.telecom.phone"),
            FormField(field_id="email", label="Email Address", type="email", required=False, section="demographics", fhir_mapping="Patient.telecom.email"),
            FormField(field_id="address", label="Home Address", type="string", required=True, section="demographics", fhir_mapping="Patient.address"),
            FormField(field_id="insurance_provider", label="Insurance Provider", type="string", required=True, section="insurance", fhir_mapping="Coverage.payor"),
            FormField(field_id="insurance_id", label="Member ID / Policy Number", type="string", required=True, section="insurance", fhir_mapping="Coverage.identifier"),
            FormField(field_id="emergency_contact_name", label="Emergency Contact Name", type="string", required=True, section="demographics", fhir_mapping="Patient.contact.name"),
            FormField(field_id="emergency_contact_phone", label="Emergency Contact Phone", type="phone", required=True, section="demographics", fhir_mapping="Patient.contact.telecom"),
            FormField(field_id="emergency_contact_relation", label="Relationship to Patient", type="string", required=True, section="demographics", fhir_mapping="Patient.contact.relationship"),
            FormField(field_id="reason_for_visit", label="Reason for Visit", type="string", required=True, section="medical_history"),
            FormField(field_id="current_medications", label="Current Medications", type="string", required=False, section="medical_history", fhir_mapping="MedicationRequest"),
            FormField(field_id="known_allergies", label="Known Allergies", type="string", required=False, section="medical_history", fhir_mapping="AllergyIntolerance"),
            FormField(field_id="consent_signature", label="Patient Signature", type="signature", required=True, section="consent"),
            FormField(field_id="consent_date", label="Date Signed", type="date", required=True, section="consent"),
        ],
    ),
    "template-002": FormTemplate(
        template_id="template-002",
        name="Cardiology Pre-Visit Form",
        description="Cardiology-specific intake including cardiac history and current symptoms.",
        category="cardiology",
        fields=[
            FormField(field_id="full_name", label="Full Name", type="string", required=True, section="demographics", fhir_mapping="Patient.name"),
            FormField(field_id="date_of_birth", label="Date of Birth", type="date", required=True, section="demographics", fhir_mapping="Patient.birthDate"),
            FormField(field_id="phone", label="Phone Number", type="phone", required=True, section="demographics", fhir_mapping="Patient.telecom.phone"),
            FormField(field_id="insurance_provider", label="Insurance Provider", type="string", required=True, section="insurance", fhir_mapping="Coverage.payor"),
            FormField(field_id="insurance_id", label="Member ID", type="string", required=True, section="insurance", fhir_mapping="Coverage.identifier"),
            FormField(field_id="chest_pain", label="Are you experiencing chest pain?", type="boolean", required=True, section="medical_history"),
            FormField(field_id="chest_pain_frequency", label="How often does chest pain occur?", type="string", required=False, section="medical_history"),
            FormField(field_id="shortness_of_breath", label="Do you experience shortness of breath?", type="boolean", required=True, section="medical_history"),
            FormField(field_id="cardiac_history", label="Previous cardiac diagnoses or procedures", type="string", required=False, section="medical_history", fhir_mapping="Condition"),
            FormField(field_id="current_medications", label="Current Medications (include dosages)", type="string", required=True, section="medical_history", fhir_mapping="MedicationRequest"),
            FormField(field_id="known_allergies", label="Drug Allergies", type="string", required=False, section="medical_history", fhir_mapping="AllergyIntolerance"),
            FormField(field_id="family_cardiac_history", label="Family history of heart disease?", type="boolean", required=False, section="medical_history"),
            FormField(field_id="smoking_status", label="Do you currently smoke or use tobacco?", type="boolean", required=False, section="medical_history"),
            FormField(field_id="consent_signature", label="Patient Signature", type="signature", required=True, section="consent"),
            FormField(field_id="consent_date", label="Date Signed", type="date", required=True, section="consent"),
        ],
    ),
    "template-003": FormTemplate(
        template_id="template-003",
        name="Post-Op Follow-Up Assessment",
        description="Used after surgical procedures to assess recovery status.",
        category="post_op",
        fields=[
            FormField(field_id="full_name", label="Full Name", type="string", required=True, section="demographics", fhir_mapping="Patient.name"),
            FormField(field_id="date_of_birth", label="Date of Birth", type="date", required=True, section="demographics", fhir_mapping="Patient.birthDate"),
            FormField(field_id="procedure_name", label="Procedure Performed", type="string", required=True, section="medical_history"),
            FormField(field_id="procedure_date", label="Date of Procedure", type="date", required=True, section="medical_history"),
            FormField(field_id="pain_level", label="Current Pain Level (0-10)", type="number", required=True, section="medical_history"),
            FormField(field_id="wound_condition", label="Describe wound/incision site condition", type="string", required=True, section="medical_history"),
            FormField(field_id="fever_present", label="Have you had a fever above 101°F?", type="boolean", required=True, section="medical_history"),
            FormField(field_id="current_medications", label="Current Medications", type="string", required=True, section="medical_history", fhir_mapping="MedicationRequest"),
            FormField(field_id="activity_level", label="Describe your current activity level", type="string", required=False, section="medical_history"),
            FormField(field_id="consent_signature", label="Patient Signature", type="signature", required=True, section="consent"),
            FormField(field_id="consent_date", label="Date Signed", type="date", required=True, section="consent"),
        ],
    ),
}

_QUESTION_BANK: Dict[str, FollowUpQuestion] = {
    "qb-001": FollowUpQuestion(
        question_id="qb-001",
        text="On a scale of 0 to 10, how would you rate your pain level today?",
        category="symptoms",
        concerning_keywords=["10", "nine", "unbearable", "severe", "excruciating"],
    ),
    "qb-002": FollowUpQuestion(
        question_id="qb-002",
        text="Are you taking all of your prescribed medications as directed?",
        category="medication",
        concerning_keywords=["no", "stopped", "forgot", "can't afford", "side effects"],
    ),
    "qb-003": FollowUpQuestion(
        question_id="qb-003",
        text="Have you experienced any new or worsening symptoms since your last visit?",
        category="symptoms",
        concerning_keywords=["chest pain", "can't breathe", "worse", "new symptom", "bleeding", "fever"],
    ),
    "qb-004": FollowUpQuestion(
        question_id="qb-004",
        text="How has your energy level been — are you able to do your normal daily activities?",
        category="activity",
        concerning_keywords=["no", "exhausted", "can't get up", "bedridden", "unable"],
    ),
    "qb-005": FollowUpQuestion(
        question_id="qb-005",
        text="Have you had any falls or felt dizzy or lightheaded?",
        category="symptoms",
        concerning_keywords=["yes", "fell", "dizzy", "fainted", "passed out"],
    ),
    "qb-006": FollowUpQuestion(
        question_id="qb-006",
        text="How has your mood been? Are you feeling anxious or down?",
        category="mood",
        concerning_keywords=["depressed", "hopeless", "hurt myself", "suicidal", "can't cope"],
    ),
    "qb-007": FollowUpQuestion(
        question_id="qb-007",
        text="Are you getting enough sleep — roughly how many hours a night?",
        category="mood",
        concerning_keywords=["none", "zero", "can't sleep", "insomnia", "awake all night"],
    ),
    "qb-008": FollowUpQuestion(
        question_id="qb-008",
        text="Have you had any fever above 101°F or chills since your procedure?",
        category="symptoms",
        concerning_keywords=["yes", "fever", "chills", "hot", "sweating"],
    ),
    "qb-009": FollowUpQuestion(
        question_id="qb-009",
        text="How does your incision or wound site look — any redness, swelling, or discharge?",
        category="symptoms",
        concerning_keywords=["red", "swollen", "pus", "discharge", "opened up", "bleeding"],
    ),
    "qb-010": FollowUpQuestion(
        question_id="qb-010",
        text="Have you had any shortness of breath or chest tightness?",
        category="symptoms",
        concerning_keywords=["yes", "can't breathe", "chest pain", "tightness", "gasping"],
    ),
    "qb-011": FollowUpQuestion(
        question_id="qb-011",
        text="Are you eating and drinking normally?",
        category="activity",
        concerning_keywords=["no", "can't eat", "vomiting", "nausea", "nothing"],
    ),
    "qb-012": FollowUpQuestion(
        question_id="qb-012",
        text="Do you have any questions for your care team from since your discharge?",
        category="custom",
    ),
}


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    return value


def _as_model(model_cls: Type[T], record: Any) -> T:
    data = {
        column.name: getattr(record, column.name)
        for column in record.__table__.columns
    }
    return model_cls(**data)


def _wait_for_database(max_attempts: int = 30, sleep_seconds: float = 1.0):
    last_error: Exception | None = None
    for _ in range(max_attempts):
        try:
            with engine.connect():
                return
        except Exception as exc:
            last_error = exc
            time.sleep(sleep_seconds)
    raise RuntimeError(f"Database unavailable after {max_attempts} attempts: {last_error}")


def _seed_if_empty(db):
    if not db.scalar(select(PatientRecord.patient_id).limit(1)):
        db.add_all(PatientRecord(**payload) for payload in _SEED_PATIENTS.values())

    if not db.scalar(select(VisitRecord.visit_id).limit(1)):
        db.add_all(VisitRecord(**payload) for payload in _SEED_VISITS.values())

    if not db.scalar(select(StaffUserRecord.staff_id).limit(1)):
        db.add_all(StaffUserRecord(**payload) for payload in _SEED_STAFF.values())

    if not db.scalar(select(FormTemplateRecord.template_id).limit(1)):
        db.add_all(
            FormTemplateRecord(
                template_id=template.template_id,
                name=template.name,
                description=template.description,
                category=template.category,
                fields=[field.model_dump() for field in template.fields],
            )
            for template in _TEMPLATES.values()
        )

    if not db.scalar(select(AssignedFormRecord.assignment_id).limit(1)):
        db.add_all(AssignedFormRecord(**payload) for payload in _SEED_FORMS.values())

    if not db.scalar(select(QuestionBankRecord.question_id).limit(1)):
        db.add_all(
            QuestionBankRecord(
                question_id=question.question_id,
                text=question.text,
                category=question.category,
                is_custom=question.is_custom,
                concerning_keywords=question.concerning_keywords,
            )
            for question in _QUESTION_BANK.values()
        )

    if not db.scalar(select(FollowUpTaskRecord.task_id).limit(1)):
        db.add_all(
            FollowUpTaskRecord(
                **{k: v for k, v in payload.items() if k != "question_ids"},
                questions=[
                    _QUESTION_BANK[question_id].model_dump()
                    for question_id in payload["question_ids"]
                    if question_id in _QUESTION_BANK
                ],
                flags=[],
                session_id=payload.get("session_id"),
                results_summary=payload.get("results_summary"),
            )
            for payload in _SEED_TASKS.values()
        )


def init_db():
    global _INITIALIZED
    if _INITIALIZED:
        return

    with _INIT_LOCK:
        if _INITIALIZED:
            return
        _wait_for_database()
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            _seed_if_empty(db)
            db.commit()
        _INITIALIZED = True


@contextmanager
def _session_scope():
    init_db()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _upsert(db, record_cls, pk_field: str, payload: dict):
    record = db.get(record_cls, payload[pk_field])
    if record is None:
        record = record_cls(**payload)
        db.add(record)
    else:
        for key, value in payload.items():
            setattr(record, key, value)
    db.flush()
    return record


def get_all_patients() -> List[Patient]:
    with _session_scope() as db:
        rows = db.scalars(select(PatientRecord).order_by(PatientRecord.last_name, PatientRecord.first_name)).all()
        return [_as_model(Patient, row) for row in rows]


def get_patient(patient_id: str) -> Optional[Patient]:
    with _session_scope() as db:
        row = db.get(PatientRecord, patient_id)
        return _as_model(Patient, row) if row else None


def get_reusable_field_facts(patient_id: str) -> List[ReusableFieldFact]:
    with _session_scope() as db:
        rows = db.scalars(
            select(ReusableFieldFactRecord)
            .where(ReusableFieldFactRecord.patient_id == patient_id)
            .order_by(ReusableFieldFactRecord.last_confirmed_at.desc())
        ).all()
        return [_as_model(ReusableFieldFact, row) for row in rows]


def save_reusable_field_fact(fact: ReusableFieldFact) -> ReusableFieldFact:
    with _session_scope() as db:
        existing = db.scalar(
            select(ReusableFieldFactRecord).where(
                ReusableFieldFactRecord.patient_id == fact.patient_id,
                ReusableFieldFactRecord.field_key == fact.field_key,
            )
        )
        payload = fact.model_dump()
        if existing is None:
            db.add(ReusableFieldFactRecord(**payload))
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
        db.flush()
    return fact


def get_patient_medications(patient_id: str) -> List[PatientMedication]:
    with _session_scope() as db:
        rows = db.scalars(
            select(PatientMedicationRecord)
            .where(PatientMedicationRecord.patient_id == patient_id, PatientMedicationRecord.active.is_(True))
            .order_by(PatientMedicationRecord.last_confirmed_at.desc())
        ).all()
        return [_as_model(PatientMedication, row) for row in rows]


def replace_patient_medications(patient_id: str, medications: List[PatientMedication]) -> List[PatientMedication]:
    with _session_scope() as db:
        existing = db.scalars(select(PatientMedicationRecord).where(PatientMedicationRecord.patient_id == patient_id)).all()
        for row in existing:
            db.delete(row)
        for medication in medications:
            db.add(PatientMedicationRecord(**medication.model_dump()))
        db.flush()
    return medications


def get_patient_allergies(patient_id: str) -> List[PatientAllergy]:
    with _session_scope() as db:
        rows = db.scalars(
            select(PatientAllergyRecord)
            .where(PatientAllergyRecord.patient_id == patient_id, PatientAllergyRecord.active.is_(True))
            .order_by(PatientAllergyRecord.last_confirmed_at.desc())
        ).all()
        return [_as_model(PatientAllergy, row) for row in rows]


def replace_patient_allergies(patient_id: str, allergies: List[PatientAllergy]) -> List[PatientAllergy]:
    with _session_scope() as db:
        existing = db.scalars(select(PatientAllergyRecord).where(PatientAllergyRecord.patient_id == patient_id)).all()
        for row in existing:
            db.delete(row)
        for allergy in allergies:
            db.add(PatientAllergyRecord(**allergy.model_dump()))
        db.flush()
    return allergies


def get_patient_conditions(patient_id: str) -> List[PatientCondition]:
    with _session_scope() as db:
        rows = db.scalars(
            select(PatientConditionRecord)
            .where(PatientConditionRecord.patient_id == patient_id, PatientConditionRecord.active.is_(True))
            .order_by(PatientConditionRecord.last_confirmed_at.desc())
        ).all()
        return [_as_model(PatientCondition, row) for row in rows]


def replace_patient_conditions(patient_id: str, conditions: List[PatientCondition]) -> List[PatientCondition]:
    with _session_scope() as db:
        existing = db.scalars(select(PatientConditionRecord).where(PatientConditionRecord.patient_id == patient_id)).all()
        for row in existing:
            db.delete(row)
        for condition in conditions:
            db.add(PatientConditionRecord(**condition.model_dump()))
        db.flush()
    return conditions


def create_patient(patient: Patient) -> Patient:
    with _session_scope() as db:
        _upsert(db, PatientRecord, "patient_id", patient.model_dump())
    return patient


def update_patient(patient_id: str, updates: Dict[str, Any]) -> Optional[Patient]:
    with _session_scope() as db:
        row = db.get(PatientRecord, patient_id)
        if not row:
            return None
        for key, value in updates.items():
            setattr(row, key, _normalize(value))
        db.flush()
        return _as_model(Patient, row)


def find_patient_by_identity(first_name: str, last_name: str, dob: str) -> Optional[Patient]:
    with _session_scope() as db:
        row = db.scalar(
            select(PatientRecord).where(
                PatientRecord.first_name.ilike(first_name),
                PatientRecord.last_name.ilike(last_name),
                PatientRecord.date_of_birth == dob,
            )
        )
        return _as_model(Patient, row) if row else None


def get_all_visits(patient_id: Optional[str] = None) -> List[ScheduledVisit]:
    with _session_scope() as db:
        stmt = select(VisitRecord)
        if patient_id:
            stmt = stmt.where(VisitRecord.patient_id == patient_id)
        stmt = stmt.order_by(VisitRecord.visit_date, VisitRecord.visit_time)
        rows = db.scalars(stmt).all()
        return [_as_model(ScheduledVisit, row) for row in rows]


def get_visit(visit_id: str) -> Optional[ScheduledVisit]:
    with _session_scope() as db:
        row = db.get(VisitRecord, visit_id)
        return _as_model(ScheduledVisit, row) if row else None


def create_visit(visit: ScheduledVisit) -> ScheduledVisit:
    with _session_scope() as db:
        _upsert(db, VisitRecord, "visit_id", visit.model_dump())
    return visit


def find_visit_by_date(patient_id: str, visit_date: str) -> Optional[ScheduledVisit]:
    with _session_scope() as db:
        row = db.scalar(
            select(VisitRecord).where(
                VisitRecord.patient_id == patient_id,
                VisitRecord.visit_date == visit_date,
            )
        )
        return _as_model(ScheduledVisit, row) if row else None


def update_visit_status(visit_id: str, status: str) -> Optional[ScheduledVisit]:
    with _session_scope() as db:
        row = db.get(VisitRecord, visit_id)
        if not row:
            return None
        row.status = status
        db.flush()
        return _as_model(ScheduledVisit, row)


def get_all_staff() -> List[StaffUser]:
    with _session_scope() as db:
        rows = db.scalars(select(StaffUserRecord).order_by(StaffUserRecord.name)).all()
        return [_as_model(StaffUser, row) for row in rows]


def get_staff(staff_id: str) -> Optional[StaffUser]:
    with _session_scope() as db:
        row = db.get(StaffUserRecord, staff_id)
        return _as_model(StaffUser, row) if row else None


def get_all_templates() -> List[FormTemplate]:
    with _session_scope() as db:
        rows = db.scalars(select(FormTemplateRecord).order_by(FormTemplateRecord.template_id)).all()
        return [_as_model(FormTemplate, row) for row in rows]


def get_template(template_id: str) -> Optional[FormTemplate]:
    with _session_scope() as db:
        row = db.get(FormTemplateRecord, template_id)
        return _as_model(FormTemplate, row) if row else None


def create_template(template: FormTemplate) -> FormTemplate:
    with _session_scope() as db:
        _upsert(
            db,
            FormTemplateRecord,
            "template_id",
            {
                "template_id": template.template_id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "fields": [field.model_dump() for field in template.fields],
            },
        )
    return template


def get_assignments_for_visit(visit_id: str) -> List[AssignedForm]:
    with _session_scope() as db:
        rows = db.scalars(
            select(AssignedFormRecord)
            .where(AssignedFormRecord.visit_id == visit_id)
            .order_by(AssignedFormRecord.assigned_at)
        ).all()
        return [_as_model(AssignedForm, row) for row in rows]


def get_assignment(assignment_id: str) -> Optional[AssignedForm]:
    with _session_scope() as db:
        row = db.get(AssignedFormRecord, assignment_id)
        return _as_model(AssignedForm, row) if row else None


def create_assignment(assignment: AssignedForm) -> AssignedForm:
    with _session_scope() as db:
        _upsert(db, AssignedFormRecord, "assignment_id", assignment.model_dump())
    return assignment


def update_assignment(assignment_id: str, updates: Dict[str, Any]) -> Optional[AssignedForm]:
    with _session_scope() as db:
        row = db.get(AssignedFormRecord, assignment_id)
        if not row:
            return None
        for key, value in updates.items():
            setattr(row, key, _normalize(value))
        db.flush()
        return _as_model(AssignedForm, row)


def get_assignment_by_form_id(form_id: str) -> Optional[AssignedForm]:
    with _session_scope() as db:
        row = db.scalar(select(AssignedFormRecord).where(AssignedFormRecord.form_id == form_id))
        return _as_model(AssignedForm, row) if row else None


def save_completed_form(completed: CompletedForm) -> CompletedForm:
    with _session_scope() as db:
        _upsert(
            db,
            CompletedFormRecord,
            "form_id",
            {
                "form_id": completed.form_id,
                "patient_id": completed.patient_id,
                "visit_id": completed.visit_id,
                "template_id": completed.template_id,
                "fields": [field.model_dump() for field in completed.fields],
                "created_at": completed.created_at or now_iso(),
            },
        )
    return completed


def get_completed_form(form_id: str) -> Optional[CompletedForm]:
    with _session_scope() as db:
        row = db.get(CompletedFormRecord, form_id)
        if not row:
            return None
        return CompletedForm(
            form_id=row.form_id,
            patient_id=row.patient_id,
            visit_id=row.visit_id,
            template_id=row.template_id,
            fields=[CompletedFormField(**field) for field in row.fields],
            created_at=row.created_at,
        )


def get_completed_forms_for_patient(patient_id: str) -> List[CompletedForm]:
    with _session_scope() as db:
        rows = db.scalars(
            select(CompletedFormRecord)
            .where(CompletedFormRecord.patient_id == patient_id)
            .order_by(CompletedFormRecord.created_at.desc())
        ).all()
        return [
            CompletedForm(
                form_id=row.form_id,
                patient_id=row.patient_id,
                visit_id=row.visit_id,
                template_id=row.template_id,
                fields=[CompletedFormField(**field) for field in row.fields],
                created_at=row.created_at,
            )
            for row in rows
        ]


def get_session(session_id: str) -> Optional[IntakeCallSession]:
    with _session_scope() as db:
        row = db.get(InterviewSessionRecord, session_id)
        return _as_model(IntakeCallSession, row) if row else None


def get_all_sessions(session_type: Optional[str] = None) -> List[IntakeCallSession]:
    with _session_scope() as db:
        stmt = select(InterviewSessionRecord).order_by(InterviewSessionRecord.created_at.desc())
        if session_type:
            stmt = stmt.where(InterviewSessionRecord.session_type == session_type)
        rows = db.scalars(stmt).all()
        return [_as_model(IntakeCallSession, row) for row in rows]


def get_sessions_for_patient(patient_id: str, session_type: Optional[str] = None) -> List[IntakeCallSession]:
    with _session_scope() as db:
        stmt = (
            select(InterviewSessionRecord)
            .where(InterviewSessionRecord.patient_id == patient_id)
            .order_by(InterviewSessionRecord.created_at.desc())
        )
        if session_type:
            stmt = stmt.where(InterviewSessionRecord.session_type == session_type)
        rows = db.scalars(stmt).all()
        return [_as_model(IntakeCallSession, row) for row in rows]


def save_session(session: IntakeCallSession) -> IntakeCallSession:
    with _session_scope() as db:
        _upsert(db, InterviewSessionRecord, "session_id", _normalize(session.model_dump()))
    return session


def update_session(session_id: str, updates: Dict[str, Any]) -> Optional[IntakeCallSession]:
    with _session_scope() as db:
        row = db.get(InterviewSessionRecord, session_id)
        if not row:
            return None
        for key, value in updates.items():
            setattr(row, key, _normalize(value))
        db.flush()
        return _as_model(IntakeCallSession, row)


def get_all_followup_tasks(patient_id: Optional[str] = None) -> List[PostDischargeFollowUpTask]:
    with _session_scope() as db:
        stmt = select(FollowUpTaskRecord)
        if patient_id:
            stmt = stmt.where(FollowUpTaskRecord.patient_id == patient_id)
        stmt = stmt.order_by(FollowUpTaskRecord.scheduled_at)
        rows = db.scalars(stmt).all()
        return [_as_model(PostDischargeFollowUpTask, row) for row in rows]


def get_followup_task(task_id: str) -> Optional[PostDischargeFollowUpTask]:
    with _session_scope() as db:
        row = db.get(FollowUpTaskRecord, task_id)
        return _as_model(PostDischargeFollowUpTask, row) if row else None


def create_followup_task(task: PostDischargeFollowUpTask) -> PostDischargeFollowUpTask:
    with _session_scope() as db:
        _upsert(db, FollowUpTaskRecord, "task_id", _normalize(task.model_dump()))
    return task


def update_followup_task(task_id: str, updates: Dict[str, Any]) -> Optional[PostDischargeFollowUpTask]:
    with _session_scope() as db:
        row = db.get(FollowUpTaskRecord, task_id)
        if not row:
            return None
        for key, value in updates.items():
            setattr(row, key, _normalize(value))
        db.flush()
        return _as_model(PostDischargeFollowUpTask, row)


def get_responses_for_task(task_id: str) -> List[FollowUpResponse]:
    with _session_scope() as db:
        rows = db.scalars(
            select(FollowUpResponseRecord)
            .where(FollowUpResponseRecord.task_id == task_id)
            .order_by(FollowUpResponseRecord.timestamp)
        ).all()
        return [_as_model(FollowUpResponse, row) for row in rows]


def save_followup_response(response: FollowUpResponse) -> FollowUpResponse:
    with _session_scope() as db:
        _upsert(db, FollowUpResponseRecord, "response_id", response.model_dump())
    return response


def get_voice_call_session(call_sid: str) -> Optional[VoiceCallSession]:
    with _session_scope() as db:
        row = db.get(VoiceCallSessionRecord, call_sid)
        return _as_model(VoiceCallSession, row) if row else None


def save_voice_call_session(call_session: VoiceCallSession) -> VoiceCallSession:
    with _session_scope() as db:
        _upsert(db, VoiceCallSessionRecord, "call_sid", _normalize(call_session.model_dump()))
    return call_session


def update_voice_call_session(call_sid: str, updates: Dict[str, Any]) -> Optional[VoiceCallSession]:
    with _session_scope() as db:
        row = db.get(VoiceCallSessionRecord, call_sid)
        if not row:
            return None
        updates = {**updates, "updated_at": now_iso()}
        for key, value in updates.items():
            setattr(row, key, _normalize(value))
        db.flush()
        return _as_model(VoiceCallSession, row)


def get_question_bank() -> List[FollowUpQuestion]:
    with _session_scope() as db:
        rows = db.scalars(select(QuestionBankRecord).order_by(QuestionBankRecord.question_id)).all()
        return [_as_model(FollowUpQuestion, row) for row in rows]


def get_question(question_id: str) -> Optional[FollowUpQuestion]:
    with _session_scope() as db:
        row = db.get(QuestionBankRecord, question_id)
        return _as_model(FollowUpQuestion, row) if row else None


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
