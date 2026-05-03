# app/services/store.py
# Central in-memory mock data store.
# Patient/visit/staff/form/task data is loaded from seed_data.py.
# Routes and services import from here rather than maintaining their own state.
#
# Replace with a real database (SQLAlchemy + Alembic) when ready for production.

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.schemas import (
    AssignedForm,
    FollowUpQuestion,
    FollowUpResponse,
    FormField,
    FormTemplate,
    IntakeCallSession,
    Patient,
    PostDischargeFollowUpTask,
    ScheduledVisit,
    StaffUser,
    VoiceCallSession,
)
from app.services.seed_data import ASSIGNED_FORMS as _SEED_FORMS
from app.services.seed_data import FOLLOWUP_TASKS as _SEED_TASKS
from app.services.seed_data import PATIENTS as _SEED_PATIENTS
from app.services.seed_data import STAFF as _SEED_STAFF
from app.services.seed_data import VISITS as _SEED_VISITS

_RUNTIME_STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "runtime_store.json"


# ════════════════════════════════════════════════════════════════════════════
# Patients
# ════════════════════════════════════════════════════════════════════════════

_PATIENTS: Dict[str, Patient] = {
    pid: Patient(**data) for pid, data in _SEED_PATIENTS.items()
}


# ════════════════════════════════════════════════════════════════════════════
# Scheduled Visits
# ════════════════════════════════════════════════════════════════════════════

_VISITS: Dict[str, ScheduledVisit] = {
    vid: ScheduledVisit(**data) for vid, data in _SEED_VISITS.items()
}


# ════════════════════════════════════════════════════════════════════════════
# Staff Users
# ════════════════════════════════════════════════════════════════════════════

_STAFF: Dict[str, StaffUser] = {
    sid: StaffUser(**data) for sid, data in _SEED_STAFF.items()
}


# ════════════════════════════════════════════════════════════════════════════
# Form Templates
# ════════════════════════════════════════════════════════════════════════════

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


# ════════════════════════════════════════════════════════════════════════════
# Assigned Forms (template linked to a specific visit)
# ════════════════════════════════════════════════════════════════════════════

_ASSIGNED_FORMS: Dict[str, AssignedForm] = {
    aid: AssignedForm(**data) for aid, data in _SEED_FORMS.items()
}


# ════════════════════════════════════════════════════════════════════════════
# Follow-Up Question Bank
# ════════════════════════════════════════════════════════════════════════════

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


# ════════════════════════════════════════════════════════════════════════════
# Runtime collections (populated at runtime, start empty)
# ════════════════════════════════════════════════════════════════════════════

_SESSIONS: Dict[str, IntakeCallSession] = {}
_FOLLOWUP_RESPONSES: Dict[str, FollowUpResponse] = {}
_VOICE_CALL_SESSIONS: Dict[str, VoiceCallSession] = {}

# Seed follow-up tasks from seed_data, resolving question IDs to full objects
_FOLLOWUP_TASKS: Dict[str, PostDischargeFollowUpTask] = {
    tid: PostDischargeFollowUpTask(
        **{k: v for k, v in data.items() if k != "question_ids"},
        questions=[_QUESTION_BANK[qid] for qid in data["question_ids"] if qid in _QUESTION_BANK],
    )
    for tid, data in _SEED_TASKS.items()
}


def _persist_runtime_data():
    _RUNTIME_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "patients": {key: value.model_dump() for key, value in _PATIENTS.items()},
        "visits": {key: value.model_dump() for key, value in _VISITS.items()},
        "assigned_forms": {key: value.model_dump() for key, value in _ASSIGNED_FORMS.items()},
        "sessions": {key: value.model_dump() for key, value in _SESSIONS.items()},
        "followup_tasks": {key: value.model_dump() for key, value in _FOLLOWUP_TASKS.items()},
        "followup_responses": {key: value.model_dump() for key, value in _FOLLOWUP_RESPONSES.items()},
        "voice_call_sessions": {key: value.model_dump() for key, value in _VOICE_CALL_SESSIONS.items()},
    }
    _RUNTIME_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_runtime_data():
    if not _RUNTIME_STORE_PATH.exists():
        return

    try:
        payload = json.loads(_RUNTIME_STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return

    _PATIENTS.update({
        key: Patient(**value) for key, value in payload.get("patients", {}).items()
    })
    _VISITS.update({
        key: ScheduledVisit(**value) for key, value in payload.get("visits", {}).items()
    })
    _ASSIGNED_FORMS.update({
        key: AssignedForm(**value) for key, value in payload.get("assigned_forms", {}).items()
    })
    _SESSIONS.update({
        key: IntakeCallSession(**value) for key, value in payload.get("sessions", {}).items()
    })
    _FOLLOWUP_TASKS.update({
        key: PostDischargeFollowUpTask(**value) for key, value in payload.get("followup_tasks", {}).items()
    })
    _FOLLOWUP_RESPONSES.update({
        key: FollowUpResponse(**value) for key, value in payload.get("followup_responses", {}).items()
    })
    _VOICE_CALL_SESSIONS.update({
        key: VoiceCallSession(**value) for key, value in payload.get("voice_call_sessions", {}).items()
    })


_load_runtime_data()


# ════════════════════════════════════════════════════════════════════════════
# Patient CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_all_patients() -> List[Patient]:
    return list(_PATIENTS.values())

def get_patient(patient_id: str) -> Optional[Patient]:
    return _PATIENTS.get(patient_id)

def create_patient(patient: Patient) -> Patient:
    _PATIENTS[patient.patient_id] = patient
    _persist_runtime_data()
    return patient

def find_patient_by_identity(first_name: str, last_name: str, dob: str) -> Optional[Patient]:
    for p in _PATIENTS.values():
        if (
            p.first_name.lower() == first_name.lower()
            and p.last_name.lower() == last_name.lower()
            and p.date_of_birth == dob
        ):
            return p
    return None


# ════════════════════════════════════════════════════════════════════════════
# Visit CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_all_visits(patient_id: Optional[str] = None) -> List[ScheduledVisit]:
    visits = list(_VISITS.values())
    if patient_id:
        visits = [v for v in visits if v.patient_id == patient_id]
    return visits

def get_visit(visit_id: str) -> Optional[ScheduledVisit]:
    return _VISITS.get(visit_id)

def create_visit(visit: ScheduledVisit) -> ScheduledVisit:
    _VISITS[visit.visit_id] = visit
    _persist_runtime_data()
    return visit

def find_visit_by_date(patient_id: str, visit_date: str) -> Optional[ScheduledVisit]:
    for v in _VISITS.values():
        if v.patient_id == patient_id and v.visit_date == visit_date:
            return v
    return None

def update_visit_status(visit_id: str, status: str) -> Optional[ScheduledVisit]:
    visit = _VISITS.get(visit_id)
    if visit:
        _VISITS[visit_id] = visit.model_copy(update={"status": status})
        _persist_runtime_data()
    return _VISITS.get(visit_id)


# ════════════════════════════════════════════════════════════════════════════
# Staff CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_all_staff() -> List[StaffUser]:
    return list(_STAFF.values())

def get_staff(staff_id: str) -> Optional[StaffUser]:
    return _STAFF.get(staff_id)


# ════════════════════════════════════════════════════════════════════════════
# Form Template CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_all_templates() -> List[FormTemplate]:
    return list(_TEMPLATES.values())

def get_template(template_id: str) -> Optional[FormTemplate]:
    return _TEMPLATES.get(template_id)


# ════════════════════════════════════════════════════════════════════════════
# Assigned Form CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_assignments_for_visit(visit_id: str) -> List[AssignedForm]:
    return [a for a in _ASSIGNED_FORMS.values() if a.visit_id == visit_id]

def get_assignment(assignment_id: str) -> Optional[AssignedForm]:
    return _ASSIGNED_FORMS.get(assignment_id)

def create_assignment(assignment: AssignedForm) -> AssignedForm:
    _ASSIGNED_FORMS[assignment.assignment_id] = assignment
    _persist_runtime_data()
    return assignment

def update_assignment(assignment_id: str, updates: Dict[str, Any]) -> Optional[AssignedForm]:
    a = _ASSIGNED_FORMS.get(assignment_id)
    if a:
        _ASSIGNED_FORMS[assignment_id] = a.model_copy(update=updates)
        _persist_runtime_data()
    return _ASSIGNED_FORMS.get(assignment_id)


# ════════════════════════════════════════════════════════════════════════════
# Session CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_session(session_id: str) -> Optional[IntakeCallSession]:
    return _SESSIONS.get(session_id)

def save_session(session: IntakeCallSession) -> IntakeCallSession:
    _SESSIONS[session.session_id] = session
    _persist_runtime_data()
    return session

def update_session(session_id: str, updates: Dict[str, Any]) -> Optional[IntakeCallSession]:
    s = _SESSIONS.get(session_id)
    if s:
        _SESSIONS[session_id] = s.model_copy(update=updates)
        _persist_runtime_data()
    return _SESSIONS.get(session_id)


# ════════════════════════════════════════════════════════════════════════════
# Follow-Up Task CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_all_followup_tasks(patient_id: Optional[str] = None) -> List[PostDischargeFollowUpTask]:
    tasks = list(_FOLLOWUP_TASKS.values())
    if patient_id:
        tasks = [t for t in tasks if t.patient_id == patient_id]
    return tasks

def get_followup_task(task_id: str) -> Optional[PostDischargeFollowUpTask]:
    return _FOLLOWUP_TASKS.get(task_id)

def create_followup_task(task: PostDischargeFollowUpTask) -> PostDischargeFollowUpTask:
    _FOLLOWUP_TASKS[task.task_id] = task
    _persist_runtime_data()
    return task

def update_followup_task(task_id: str, updates: Dict[str, Any]) -> Optional[PostDischargeFollowUpTask]:
    t = _FOLLOWUP_TASKS.get(task_id)
    if t:
        _FOLLOWUP_TASKS[task_id] = t.model_copy(update=updates)
        _persist_runtime_data()
    return _FOLLOWUP_TASKS.get(task_id)


# ════════════════════════════════════════════════════════════════════════════
# Follow-Up Responses CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_responses_for_task(task_id: str) -> List[FollowUpResponse]:
    return [r for r in _FOLLOWUP_RESPONSES.values() if r.task_id == task_id]

def save_followup_response(response: FollowUpResponse) -> FollowUpResponse:
    _FOLLOWUP_RESPONSES[response.response_id] = response
    _persist_runtime_data()
    return response


# ════════════════════════════════════════════════════════════════════════════
# Voice Call Session CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_voice_call_session(call_sid: str) -> Optional[VoiceCallSession]:
    return _VOICE_CALL_SESSIONS.get(call_sid)

def save_voice_call_session(call_session: VoiceCallSession) -> VoiceCallSession:
    _VOICE_CALL_SESSIONS[call_session.call_sid] = call_session
    _persist_runtime_data()
    return call_session

def update_voice_call_session(call_sid: str, updates: Dict[str, Any]) -> Optional[VoiceCallSession]:
    call_session = _VOICE_CALL_SESSIONS.get(call_sid)
    if call_session:
        updates = {**updates, "updated_at": now_iso()}
        _VOICE_CALL_SESSIONS[call_sid] = call_session.model_copy(update=updates)
        _persist_runtime_data()
    return _VOICE_CALL_SESSIONS.get(call_sid)


# ════════════════════════════════════════════════════════════════════════════
# Question Bank
# ════════════════════════════════════════════════════════════════════════════

def get_question_bank() -> List[FollowUpQuestion]:
    return list(_QUESTION_BANK.values())

def get_question(question_id: str) -> Optional[FollowUpQuestion]:
    return _QUESTION_BANK.get(question_id)


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def new_id(prefix: str = "") -> str:
    """Generate a short unique ID with an optional prefix."""
    return f"{prefix}{uuid.uuid4().hex[:8]}"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
