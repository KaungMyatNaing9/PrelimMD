from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base


class PatientRecord(Base):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(Text, primary_key=True)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    date_of_birth: Mapped[str] = mapped_column(Text, nullable=False)
    gender: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    insurance_provider: Mapped[str | None] = mapped_column(Text)
    insurance_id: Mapped[str | None] = mapped_column(Text)
    emergency_contact_name: Mapped[str | None] = mapped_column(Text)
    emergency_contact_phone: Mapped[str | None] = mapped_column(Text)
    emergency_contact_relation: Mapped[str | None] = mapped_column(Text)


class ReusableFieldFactRecord(Base):
    __tablename__ = "reusable_field_facts"

    fact_id: Mapped[str] = mapped_column(Text, primary_key=True)
    patient_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    field_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="patient_kiosk")
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=95)
    last_confirmed_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)


class VisitRecord(Base):
    __tablename__ = "visits"

    visit_id: Mapped[str] = mapped_column(Text, primary_key=True)
    patient_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    visit_date: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    visit_time: Mapped[str] = mapped_column(Text, nullable=False)
    provider_name: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="scheduled")
    notes: Mapped[str | None] = mapped_column(Text)


class PatientMedicationRecord(Base):
    __tablename__ = "patient_medications"

    medication_id: Mapped[str] = mapped_column(Text, primary_key=True)
    patient_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    dosage: Mapped[str | None] = mapped_column(Text)
    frequency: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_confirmed_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)


class PatientAllergyRecord(Base):
    __tablename__ = "patient_allergies"

    allergy_id: Mapped[str] = mapped_column(Text, primary_key=True)
    patient_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    substance: Mapped[str] = mapped_column(Text, nullable=False)
    reaction: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_confirmed_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)


class PatientConditionRecord(Base):
    __tablename__ = "patient_conditions"

    condition_id: Mapped[str] = mapped_column(Text, primary_key=True)
    patient_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(Text)
    onset: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_confirmed_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)


class StaffUserRecord(Base):
    __tablename__ = "staff_users"

    staff_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)


class FormTemplateRecord(Base):
    __tablename__ = "form_templates"

    template_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class AssignedFormRecord(Base):
    __tablename__ = "assigned_forms"

    assignment_id: Mapped[str] = mapped_column(Text, primary_key=True)
    visit_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(Text, nullable=False)
    form_id: Mapped[str | None] = mapped_column(Text)
    assigned_by: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_at: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="assigned")


class CompletedFormRecord(Base):
    __tablename__ = "completed_forms"

    form_id: Mapped[str] = mapped_column(Text, primary_key=True)
    patient_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    visit_id: Mapped[str | None] = mapped_column(Text, index=True)
    template_id: Mapped[str | None] = mapped_column(Text)
    fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)


class QuestionBankRecord(Base):
    __tablename__ = "question_bank"

    question_id: Mapped[str] = mapped_column(Text, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    concerning_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class FollowUpTaskRecord(Base):
    __tablename__ = "followup_tasks"

    task_id: Mapped[str] = mapped_column(Text, primary_key=True)
    patient_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    visit_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="scheduled")
    questions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    session_id: Mapped[str | None] = mapped_column(Text)
    results_summary: Mapped[str | None] = mapped_column(Text)
    flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class FollowUpResponseRecord(Base):
    __tablename__ = "followup_responses"

    response_id: Mapped[str] = mapped_column(Text, primary_key=True)
    task_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flag_reason: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)


class InterviewSessionRecord(Base):
    __tablename__ = "interview_sessions"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_type: Mapped[str] = mapped_column(Text, nullable=False)
    visit_id: Mapped[str | None] = mapped_column(Text)
    task_id: Mapped[str | None] = mapped_column(Text)
    patient_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="in_progress")
    conversation: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    collected_answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(Text)
    current_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class VoiceCallSessionRecord(Base):
    __tablename__ = "voice_call_sessions"

    call_sid: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    patient_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    visit_id: Mapped[str | None] = mapped_column(Text)
    task_id: Mapped[str | None] = mapped_column(Text)
    from_phone: Mapped[str | None] = mapped_column(Text)
    to_phone: Mapped[str | None] = mapped_column(Text)
    verification_state: Mapped[str] = mapped_column(Text, nullable=False, default="pending_name")
    verification_name: Mapped[str | None] = mapped_column(Text)
    verification_name_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_dob_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unclear_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clarification_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completion_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
