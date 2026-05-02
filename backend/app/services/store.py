# app/services/store.py
# Central in-memory mock data store.
# All entities are initialized from hardcoded mock data at import time.
# Routes and services import from here rather than maintaining their own state.
#
# Replace with a real database (SQLAlchemy + Alembic) when ready for production.

import uuid
from copy import deepcopy
from datetime import datetime, timezone
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


# ════════════════════════════════════════════════════════════════════════════
# Patients
# ════════════════════════════════════════════════════════════════════════════

_PATIENTS: Dict[str, Patient] = {
    "patient-001": Patient(
        patient_id="patient-001",
        first_name="Jane",
        last_name="Smith",
        date_of_birth="1985-03-14",
        gender="female",
        phone="+15550101",
        email="jane.smith@email.com",
        address="123 Main St, Chicago, IL 60601",
        insurance_provider="BlueCross BlueShield",
        insurance_id="BCB123456789",
        emergency_contact_name="John Smith",
        emergency_contact_phone="+15550102",
        emergency_contact_relation="Spouse",
    ),
    "patient-002": Patient(
        patient_id="patient-002",
        first_name="Robert",
        last_name="Johnson",
        date_of_birth="1972-07-22",
        gender="male",
        phone="+15550201",
    ),
    "patient-003": Patient(
        patient_id="patient-003",
        first_name="Maria",
        last_name="Garcia",
        date_of_birth="1990-11-05",
        gender="female",
        phone="+15550301",
        email="maria.garcia@email.com",
        address="456 Oak Ave, Chicago, IL 60602",
        insurance_provider="Aetna",
        insurance_id="AET987654321",
        emergency_contact_name="Carlos Garcia",
        emergency_contact_phone="+15550302",
        emergency_contact_relation="Brother",
    ),
    "patient-004": Patient(
        patient_id="patient-004",
        first_name="David",
        last_name="Kim",
        date_of_birth="1968-09-30",
        gender="male",
        phone="+15550401",
        email="david.kim@email.com",
        address="789 Elm St, Chicago, IL 60603",
        insurance_provider="UnitedHealthcare",
        insurance_id="UHC456789123",
        emergency_contact_name="Susan Kim",
        emergency_contact_phone="+15550402",
        emergency_contact_relation="Spouse",
    ),
}


# ════════════════════════════════════════════════════════════════════════════
# Scheduled Visits
# ════════════════════════════════════════════════════════════════════════════

_VISITS: Dict[str, ScheduledVisit] = {
    "visit-001": ScheduledVisit(
        visit_id="visit-001",
        patient_id="patient-001",
        visit_date="2026-05-05",
        visit_time="09:30",
        provider_name="Dr. Sarah Chen",
        department="Cardiology",
        reason="Annual cardiac check-up",
        status="scheduled",
    ),
    "visit-002": ScheduledVisit(
        visit_id="visit-002",
        patient_id="patient-001",
        visit_date="2026-03-15",
        visit_time="10:00",
        provider_name="Dr. Sarah Chen",
        department="Cardiology",
        reason="Follow-up post medication change",
        status="completed",
    ),
    "visit-003": ScheduledVisit(
        visit_id="visit-003",
        patient_id="patient-002",
        visit_date="2026-05-06",
        visit_time="14:00",
        provider_name="Dr. James Williams",
        department="General Practice",
        reason="Cholesterol management review",
        status="scheduled",
    ),
    "visit-004": ScheduledVisit(
        visit_id="visit-004",
        patient_id="patient-003",
        visit_date="2026-05-07",
        visit_time="11:15",
        provider_name="Dr. James Williams",
        department="General Practice",
        reason="Post-op follow-up — appendectomy",
        status="scheduled",
    ),
    "visit-005": ScheduledVisit(
        visit_id="visit-005",
        patient_id="patient-004",
        visit_date="2026-05-08",
        visit_time="08:45",
        provider_name="Dr. Sarah Chen",
        department="Cardiology",
        reason="New patient — chest pain evaluation",
        status="scheduled",
    ),
}


# ════════════════════════════════════════════════════════════════════════════
# Staff Users
# ════════════════════════════════════════════════════════════════════════════

_STAFF: Dict[str, StaffUser] = {
    "staff-001": StaffUser(
        staff_id="staff-001",
        name="Dr. Sarah Chen",
        role="doctor",
        department="Cardiology",
        email="s.chen@clinic.example.com",
    ),
    "staff-002": StaffUser(
        staff_id="staff-002",
        name="Nurse Michael Torres",
        role="nurse",
        department="General Practice",
        email="m.torres@clinic.example.com",
    ),
    "staff-003": StaffUser(
        staff_id="staff-003",
        name="Dr. James Williams",
        role="doctor",
        department="General Practice",
        email="j.williams@clinic.example.com",
    ),
    "staff-004": StaffUser(
        staff_id="staff-004",
        name="Nurse Priya Patel",
        role="nurse",
        department="Cardiology",
        email="p.patel@clinic.example.com",
    ),
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
    "assign-001": AssignedForm(
        assignment_id="assign-001",
        visit_id="visit-001",
        template_id="template-002",
        assigned_by="staff-004",
        assigned_at="2026-04-28T10:00:00Z",
        status="assigned",
    ),
    "assign-002": AssignedForm(
        assignment_id="assign-002",
        visit_id="visit-003",
        template_id="template-001",
        assigned_by="staff-002",
        assigned_at="2026-04-29T08:30:00Z",
        status="assigned",
    ),
    "assign-003": AssignedForm(
        assignment_id="assign-003",
        visit_id="visit-004",
        template_id="template-003",
        assigned_by="staff-002",
        assigned_at="2026-04-29T09:00:00Z",
        status="assigned",
    ),
    "assign-004": AssignedForm(
        assignment_id="assign-004",
        visit_id="visit-005",
        template_id="template-002",
        assigned_by="staff-001",
        assigned_at="2026-04-30T14:00:00Z",
        status="assigned",
    ),
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
_FOLLOWUP_TASKS: Dict[str, PostDischargeFollowUpTask] = {}
_FOLLOWUP_RESPONSES: Dict[str, FollowUpResponse] = {}
_VOICE_CALL_SESSIONS: Dict[str, VoiceCallSession] = {}

# Seed one example follow-up task for demo/testing
_FOLLOWUP_TASKS["task-001"] = PostDischargeFollowUpTask(
    task_id="task-001",
    patient_id="patient-001",
    visit_id="visit-002",
    created_by="staff-001",
    scheduled_at="2026-05-03T10:00:00Z",
    status="scheduled",
    questions=[
        _QUESTION_BANK["qb-001"],
        _QUESTION_BANK["qb-002"],
        _QUESTION_BANK["qb-003"],
        _QUESTION_BANK["qb-010"],
    ],
    created_at="2026-04-28T09:00:00Z",
)


# ════════════════════════════════════════════════════════════════════════════
# Patient CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_all_patients() -> List[Patient]:
    return list(_PATIENTS.values())

def get_patient(patient_id: str) -> Optional[Patient]:
    return _PATIENTS.get(patient_id)

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

def find_visit_by_date(patient_id: str, visit_date: str) -> Optional[ScheduledVisit]:
    for v in _VISITS.values():
        if v.patient_id == patient_id and v.visit_date == visit_date:
            return v
    return None

def update_visit_status(visit_id: str, status: str) -> Optional[ScheduledVisit]:
    visit = _VISITS.get(visit_id)
    if visit:
        _VISITS[visit_id] = visit.model_copy(update={"status": status})
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
    return assignment

def update_assignment(assignment_id: str, updates: Dict[str, Any]) -> Optional[AssignedForm]:
    a = _ASSIGNED_FORMS.get(assignment_id)
    if a:
        _ASSIGNED_FORMS[assignment_id] = a.model_copy(update=updates)
    return _ASSIGNED_FORMS.get(assignment_id)


# ════════════════════════════════════════════════════════════════════════════
# Session CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_session(session_id: str) -> Optional[IntakeCallSession]:
    return _SESSIONS.get(session_id)

def save_session(session: IntakeCallSession) -> IntakeCallSession:
    _SESSIONS[session.session_id] = session
    return session

def update_session(session_id: str, updates: Dict[str, Any]) -> Optional[IntakeCallSession]:
    s = _SESSIONS.get(session_id)
    if s:
        _SESSIONS[session_id] = s.model_copy(update=updates)
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
    return task

def update_followup_task(task_id: str, updates: Dict[str, Any]) -> Optional[PostDischargeFollowUpTask]:
    t = _FOLLOWUP_TASKS.get(task_id)
    if t:
        _FOLLOWUP_TASKS[task_id] = t.model_copy(update=updates)
    return _FOLLOWUP_TASKS.get(task_id)


# ════════════════════════════════════════════════════════════════════════════
# Follow-Up Responses CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_responses_for_task(task_id: str) -> List[FollowUpResponse]:
    return [r for r in _FOLLOWUP_RESPONSES.values() if r.task_id == task_id]

def save_followup_response(response: FollowUpResponse) -> FollowUpResponse:
    _FOLLOWUP_RESPONSES[response.response_id] = response
    return response


# ════════════════════════════════════════════════════════════════════════════
# Voice Call Session CRUD
# ════════════════════════════════════════════════════════════════════════════

def get_voice_call_session(call_sid: str) -> Optional[VoiceCallSession]:
    return _VOICE_CALL_SESSIONS.get(call_sid)

def save_voice_call_session(call_session: VoiceCallSession) -> VoiceCallSession:
    _VOICE_CALL_SESSIONS[call_session.call_sid] = call_session
    return call_session

def update_voice_call_session(call_sid: str, updates: Dict[str, Any]) -> Optional[VoiceCallSession]:
    call_session = _VOICE_CALL_SESSIONS.get(call_sid)
    if call_session:
        updates = {**updates, "updated_at": now_iso()}
        _VOICE_CALL_SESSIONS[call_sid] = call_session.model_copy(update=updates)
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
