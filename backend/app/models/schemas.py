# app/models/schemas.py
# Pydantic request/response models shared across all routes.
# All teammates should add their models here to keep types in one place.
#
# TODO: AI       - add InterviewStartRequest, InterviewStartResponse
# TODO: AI       - add InterviewRespondRequest, InterviewRespondResponse
# TODO: AI       - add SessionSummary with triage fields (risk_level, chief_complaint, routing)
# TODO: Voice    - add TranscribeResponse, SynthesizeRequest
# TODO: Report   - add IntakeReport model matching shared/types/interview.schema.json
# TODO: Scheduling - add AppointmentSlot, BookingRequest, BookingConfirmation

from pydantic import BaseModel


# ── Placeholder base models ───────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str


# TODO: each teammate — add domain models below in clearly marked sections
