# app/models/schemas.py
# Pydantic request/response models shared across all routes.

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str


# ── Voice ─────────────────────────────────────────────────────────────────────

class TranscribeResponse(BaseModel):
    success: bool
    transcript: str
    confidence: Optional[float] = None
    language: Optional[str] = None
    duration: Optional[float] = None
    raw: Optional[Any] = None


# ── Forms / Agent brain (Person 2) ───────────────────────────────────────────

class FormField(BaseModel):
    field_id: str
    label: str
    type: str                        # string | date | phone | boolean | email | signature
    required: bool
    section: str                     # demographics | insurance | medical_history | consent
    fhir_mapping: Optional[str] = None  # e.g. "Patient.birthDate"


class FormSchema(BaseModel):
    form_id: str
    form_name: str
    fields: List[FormField]


class PrefilledField(BaseModel):
    field_id: str
    value: Any
    source: Literal["ehr", "patient_call", "patient_kiosk"]
    confidence: float
    needs_review: bool = False


class MissingField(BaseModel):
    field_id: str
    label: str
    question: str       # conversational version: "What is your date of birth?"
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
    missing_fields: List[MissingField]   # field-level, for internal tracking
    questions: List["CompoundQuestion"] = []  # compound questions for the call
    stats: FormStats


class CompoundQuestion(BaseModel):
    question_id: str          # e.g. "q1", "q2"
    question: str             # natural compound question covering 1-4 fields
    field_ids: List[str]      # which fields this question fills
    required: bool            # true if any covered field is required


class CallResponseItem(BaseModel):
    question_id: str          # matches CompoundQuestion.question_id
    raw_answer: str
    timestamp: str


class CallResponses(BaseModel):
    call_id: str
    status: Literal["completed", "partial", "failed"]
    responses: List[CallResponseItem]
    reason_for_visit: Optional[str] = None   # captured from opening question open_1


class CompletedFormField(BaseModel):
    field_id: str
    value: Any
    source: str
    needs_review: bool = False


class CompletedForm(BaseModel):
    form_id: str
    patient_id: str
    fields: List[CompletedFormField]


# ── Clinical brief (Person 2 → Report teammate) ──────────────────────────────

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
    extracted_fields: List[Dict[str, str]]   # [{label, value, source}]
    transcript: List[TranscriptTurn]


# ── Communication agent (Person 3) ───────────────────────────────────────────

class OpeningQuestion(BaseModel):
    question_id: str                    # "open_0", "open_1" — always prepended
    question: str
    purpose: str                        # "identity_verification" | "reason_for_visit"


class QuestionsPayload(BaseModel):
    call_id: str
    patient_name: str
    opening: List[OpeningQuestion]      # always asked first — identity + reason for visit
    questions: List[CompoundQuestion]   # form-filling questions
    estimated_minutes: int


class ConversationTurn(BaseModel):
    role: Literal["ai", "patient"]
    content: str


class NextQuestionRequest(BaseModel):
    form_id: str
    conversation: List[ConversationTurn]   # full exchange so far, including opening


class NextQuestionResponse(BaseModel):
    question: Optional[str]                # null when done
    field_ids: List[str]
    done: bool
