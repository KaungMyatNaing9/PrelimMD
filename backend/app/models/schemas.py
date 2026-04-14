# app/models/schemas.py
# Pydantic request/response models shared across all routes.
# All teammates should add their models here to keep types in one place.
#
# TODO: AI       - add InterviewStartRequest, InterviewStartResponse
# TODO: AI       - add InterviewRespondRequest, InterviewRespondResponse
# TODO: AI       - add SessionSummary with triage fields (risk_level, chief_complaint, routing)
# TODO: Report   - add IntakeReport model matching shared/types/interview.schema.json
# TODO: Scheduling - add AppointmentSlot, BookingRequest, BookingConfirmation

from typing import Any, Optional
from pydantic import BaseModel


# ── Placeholder base models ───────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str


# ── Voice ─────────────────────────────────────────────────────────────────────

class TranscribeResponse(BaseModel):
    success: bool
    transcript: str
    confidence: Optional[float] = None   # 0.0–1.0, if returned by Deepgram
    language: Optional[str] = None       # detected language code, e.g. "en"
    duration: Optional[float] = None     # audio duration in seconds
    raw: Optional[Any] = None            # full Deepgram response for downstream use


# TODO: each teammate — add domain models below in clearly marked sections
