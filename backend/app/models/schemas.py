# app/models/schemas.py
# Pydantic request/response models shared across all routes.
# All teammates should agree on changes here before modifying.

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ════════════════════════════════════════════════════════════════════════════
# Health
# ════════════════════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    status: str


# ════════════════════════════════════════════════════════════════════════════
# Patient
# ════════════════════════════════════════════════════════════════════════════

class Patient(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: str          # YYYY-MM-DD
    gender: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class CreatePatientRequest(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None


# ════════════════════════════════════════════════════════════════════════════
# Scheduled Visit
# ════════════════════════════════════════════════════════════════════════════

class ScheduledVisit(BaseModel):
    visit_id: str
    patient_id: str
    visit_date: str             # YYYY-MM-DD
    visit_time: str             # HH:MM (24h)
    provider_name: str
    department: str
    reason: Optional[str] = None
    status: Literal["scheduled", "checked_in", "completed", "cancelled"] = "scheduled"
    notes: Optional[str] = None


class CreateVisitRequest(BaseModel):
    patient_id: str
    visit_date: str
    visit_time: str
    provider_name: str
    department: str
    reason: Optional[str] = None
    notes: Optional[str] = None


# ════════════════════════════════════════════════════════════════════════════
# Staff User
# ════════════════════════════════════════════════════════════════════════════

class StaffUser(BaseModel):
    staff_id: str
    name: str
    role: Literal["nurse", "doctor", "admin"]
    department: str
    email: str


# ════════════════════════════════════════════════════════════════════════════
# Form Template & Fields
# ════════════════════════════════════════════════════════════════════════════

class FormField(BaseModel):
    field_id: str
    label: str
    type: str                   # string | date | phone | boolean | email | signature | number
    required: bool
    section: str                # demographics | insurance | medical_history | consent | other
    fhir_mapping: Optional[str] = None


class FormTemplate(BaseModel):
    template_id: str
    name: str
    description: str
    category: str               # general_intake | cardiology | post_op | neurology | etc.
    fields: List[FormField]


class FormSchema(BaseModel):
    """Parsed/generated form schema (from uploaded PDF or derived from a template)."""
    form_id: str
    form_name: str
    fields: List[FormField]


# ════════════════════════════════════════════════════════════════════════════
# Assigned Form (template linked to a visit)
# ════════════════════════════════════════════════════════════════════════════

class AssignedForm(BaseModel):
    assignment_id: str
    visit_id: str
    template_id: str
    form_id: Optional[str] = None       # set after prefill runs
    assigned_by: str                    # staff_id
    assigned_at: str                    # ISO datetime
    status: Literal[
        "assigned", "prefilled", "in_call", "completed", "signed"
    ] = "assigned"


class AssignFormRequest(BaseModel):
    visit_id: str
    template_id: str
    assigned_by: str            # staff_id


class UploadTemplateResponse(BaseModel):
    template: FormTemplate
    parsed_schema: FormSchema
    message: str


# ════════════════════════════════════════════════════════════════════════════
# Prefilled / Completed Form
# ════════════════════════════════════════════════════════════════════════════

class PrefilledField(BaseModel):
    field_id: str
    value: Any
    source: Literal["ehr", "patient_call", "patient_kiosk"]
    confidence: float
    needs_review: bool = False
    last_confirmed_at: Optional[str] = None


class MissingField(BaseModel):
    field_id: str
    label: str
    question: str               # conversational version: "What is your date of birth?"
    type: str
    required: bool


class FormStats(BaseModel):
    total: int
    filled: int
    missing: int


class PrefilledForm(BaseModel):
    form_id: str
    patient_id: str
    filled_fields: List[PrefilledField]
    missing_fields: List[MissingField]
    questions: List["CompoundQuestion"] = []
    stats: FormStats


class CompoundQuestion(BaseModel):
    question_id: str
    question: str
    field_ids: List[str]
    required: bool


class CompletedFormField(BaseModel):
    field_id: str
    value: Any
    source: str
    needs_review: bool = False


class CompletedForm(BaseModel):
    form_id: str
    patient_id: str
    visit_id: Optional[str] = None
    template_id: Optional[str] = None
    fields: List[CompletedFormField]
    created_at: Optional[str] = None


# ════════════════════════════════════════════════════════════════════════════
# Intake Call Session
# ════════════════════════════════════════════════════════════════════════════

class SessionTurn(BaseModel):
    turn_id: str
    role: Literal["ai", "patient"]
    content: str
    timestamp: str
    field_ids_targeted: List[str] = []


class IntakeCallSession(BaseModel):
    session_id: str
    session_type: Literal["intake", "followup"]
    visit_id: Optional[str] = None
    task_id: Optional[str] = None
    patient_id: str
    status: Literal["in_progress", "completed", "abandoned"] = "in_progress"
    conversation: List[SessionTurn] = []
    collected_answers: Dict[str, Any] = {}
    flags: List[str] = []
    created_at: str
    completed_at: Optional[str] = None
    current_question_index: int = 0


class StartSessionRequest(BaseModel):
    session_type: Literal["intake", "followup"]
    visit_id: Optional[str] = None      # required when session_type == "intake"
    task_id: Optional[str] = None       # required when session_type == "followup"


class AnswerRequest(BaseModel):
    session_id: str
    answer: str


class AnswerResponse(BaseModel):
    session_id: str
    next_question: Optional[str] = None
    field_ids_targeted: List[str] = []
    is_done: bool = False
    flagged: bool = False
    flag_reason: Optional[str] = None


# ════════════════════════════════════════════════════════════════════════════
# Post-Discharge Follow-Up
# ════════════════════════════════════════════════════════════════════════════

class FollowUpQuestion(BaseModel):
    question_id: str
    text: str
    category: str               # symptoms | medication | mood | activity | custom
    is_custom: bool = False
    concerning_keywords: List[str] = []


class PostDischargeFollowUpTask(BaseModel):
    task_id: str
    patient_id: str
    visit_id: str
    created_by: str             # staff_id
    scheduled_at: str           # ISO datetime
    status: Literal[
        "scheduled", "in_progress", "completed", "failed", "cancelled"
    ] = "scheduled"
    questions: List[FollowUpQuestion] = []
    session_id: Optional[str] = None
    results_summary: Optional[str] = None
    flags: List[str] = []
    created_at: str


class ScheduleFollowUpRequest(BaseModel):
    patient_id: str
    visit_id: str
    created_by: str             # staff_id
    scheduled_at: str           # ISO datetime when the call should happen
    question_bank_ids: List[str] = []   # IDs from the question bank
    custom_questions: List[str] = []    # free-text questions added by the doctor


class FollowUpResponse(BaseModel):
    response_id: str
    task_id: str
    question_id: str
    answer: str
    flagged: bool = False
    flag_reason: Optional[str] = None
    timestamp: str


# ════════════════════════════════════════════════════════════════════════════
# Patient Check-In
# ════════════════════════════════════════════════════════════════════════════

class PatientValidateRequest(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str          # YYYY-MM-DD
    appointment_date: str       # YYYY-MM-DD


class PatientValidateResponse(BaseModel):
    valid: bool
    patient: Optional[Patient] = None
    visit: Optional[ScheduledVisit] = None
    message: str


class CheckInField(BaseModel):
    field_id: str
    label: str
    type: str
    section: str
    required: bool
    prefilled_value: Optional[Any] = None
    source: Optional[str] = None        # "ehr" | "patient_call" | None
    last_confirmed_at: Optional[str] = None
    needs_confirmation: bool = False
    is_missing: bool = False


class ReusableFieldFact(BaseModel):
    fact_id: str
    patient_id: str
    field_key: str
    value: str
    source: str
    confidence: int = 95
    last_confirmed_at: str


class PatientMedication(BaseModel):
    medication_id: str
    patient_id: str
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    active: bool = True
    last_confirmed_at: str


class PatientAllergy(BaseModel):
    allergy_id: str
    patient_id: str
    substance: str
    reaction: Optional[str] = None
    severity: Optional[str] = None
    active: bool = True
    last_confirmed_at: str


class PatientCondition(BaseModel):
    condition_id: str
    patient_id: str
    condition: str
    status: Optional[str] = None
    onset: Optional[str] = None
    active: bool = True
    last_confirmed_at: str


class CheckInFormGroup(BaseModel):
    assignment_id: str
    form_name: str
    fields: List[CheckInField]


class CheckInFormsResponse(BaseModel):
    visit_id: str
    patient_id: str
    forms: List[CheckInFormGroup]
    total_missing: int
    total_needs_confirmation: int


class CheckInSubmitRequest(BaseModel):
    answers: Dict[str, Any]     # field_id -> value


class CheckInSubmitResponse(BaseModel):
    visit_id: str
    saved_fields: int
    message: str


class CheckInSignRequest(BaseModel):
    signature: str              # typed full name or "ACCEPTED"
    signed_at: str              # ISO datetime


class CheckInSignResponse(BaseModel):
    visit_id: str
    signed: bool
    message: str


class CheckInScannedField(BaseModel):
    field_id: str
    label: str
    value: Any
    confidence: float
    field_type: str
    section: str
    source: str = "camera_scan"


class CheckInScanResponse(BaseModel):
    visit_id: str
    scanned_fields: List[CheckInScannedField]
    applied_count: int
    ocr_preview: Optional[str] = None
    message: str


class NewPatientCheckInRequest(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    phone: str
    appointment_date: str
    appointment_time: str
    reason_for_visit: str
    email: Optional[str] = None
    address: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    department: str = "General Medicine"
    provider_name: str = "Care Team"
    template_id: str = "template-001"
    assigned_by: str = "staff-001"


class NewPatientCheckInResponse(BaseModel):
    patient: Patient
    visit: ScheduledVisit
    assignment_id: str
    message: str


class IntakeFormOverview(BaseModel):
    assignment_id: str
    template_id: str
    form_name: str
    status: str
    total_fields: int
    filled_fields: int
    remaining_fields: int
    call_remaining_fields: int
    completion_percent: int
    remaining_field_labels: List[str] = []
    call_questions: List[str] = []


class IntakeOverviewResponse(BaseModel):
    visit_id: str
    patient_id: str
    total_forms: int
    total_fields: int
    filled_fields: int
    remaining_fields: int
    call_remaining_fields: int
    completion_percent: int
    forms: List[IntakeFormOverview]


class IntakeCallScheduleResponse(BaseModel):
    visit_id: str
    session_id: str
    scheduled_at: str
    status: str
    remaining_fields: int
    call_remaining_fields: int
    patient_phone: Optional[str] = None
    voice_start_path: str
    note: str


# ════════════════════════════════════════════════════════════════════════════
# Voice
# ════════════════════════════════════════════════════════════════════════════

class TranscribeResponse(BaseModel):
    success: bool
    transcript: str
    confidence: Optional[float] = None
    language: Optional[str] = None
    duration: Optional[float] = None
    raw: Optional[Any] = None


class VoiceAnswerRequest(BaseModel):
    session_id: str
    audio_text: str             # caller passes transcript; backend does not re-transcribe here


class VoiceAnswerResponse(BaseModel):
    session_id: str
    ai_text: str                # text of the AI's next question or closing
    audio_url: Optional[str] = None   # ElevenLabs audio URL if available
    is_done: bool = False
    flagged: bool = False


class VoiceCallSession(BaseModel):
    call_sid: str
    session_id: str
    mode: Literal["intake", "followup"]
    patient_id: str
    visit_id: Optional[str] = None
    task_id: Optional[str] = None
    from_phone: Optional[str] = None
    to_phone: Optional[str] = None
    verification_state: Literal["pending_name", "pending_dob", "verified", "failed"] = "pending_name"
    verification_name: Optional[str] = None
    verification_name_attempts: int = 0
    verification_dob_attempts: int = 0
    current_question_index: int = 0
    retry_count: int = 0
    unclear_count: int = 0
    clarification_attempts: int = 0
    completed: bool = False
    completion_reason: Optional[str] = None
    created_at: str
    updated_at: str
    context: Dict[str, Any] = Field(default_factory=dict)


class VoiceOutboundCallRequest(BaseModel):
    mode: Literal["intake", "followup"]
    session_id: str
    to_phone: str


class VoiceOutboundCallResponse(BaseModel):
    queued: bool
    call_sid: Optional[str] = None
    session_id: str
    mode: Literal["intake", "followup"]
    to_phone: str
    webhook_url: str


# ════════════════════════════════════════════════════════════════════════════
# Legacy call flow (kept for backward compatibility with forms/calls routes)
# ════════════════════════════════════════════════════════════════════════════

class CallResponseItem(BaseModel):
    question_id: str
    raw_answer: str
    timestamp: str


class CallResponses(BaseModel):
    call_id: str
    status: Literal["completed", "partial", "failed"]
    responses: List[CallResponseItem]
    reason_for_visit: Optional[str] = None


class OpeningQuestion(BaseModel):
    question_id: str
    question: str
    purpose: str                # "identity_verification" | "reason_for_visit"


class QuestionsPayload(BaseModel):
    call_id: str
    patient_name: str
    opening: List[OpeningQuestion]
    questions: List[CompoundQuestion]
    estimated_minutes: int


class ConversationTurn(BaseModel):
    role: Literal["ai", "patient"]
    content: str


class NextQuestionRequest(BaseModel):
    form_id: str
    conversation: List[ConversationTurn]


class NextQuestionResponse(BaseModel):
    question: Optional[str] = None
    field_ids: List[str]
    done: bool


# ════════════════════════════════════════════════════════════════════════════
# Clinical Brief / Report
# ════════════════════════════════════════════════════════════════════════════

class TranscriptTurn(BaseModel):
    id: str
    role: Literal["ai", "patient"]
    content: str
    timestamp: str
    source: Literal["system", "typed", "voice"] = "system"


class ClinicalBrief(BaseModel):
    report_id: str
    form_id: str
    patient_id: str
    created_at: str
    chief_complaint: str
    risk_level: Literal["low", "moderate", "high", "emergency"]
    recommended_routing: str
    summary: str
    notes: str
    missing_information: List[str]
    extracted_fields: List[Dict[str, str]]
    transcript: List[TranscriptTurn]
