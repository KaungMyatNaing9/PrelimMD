# app/main.py
# FastAPI application entry point.
# Registers all routers and configures middleware.

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import (
    calls,
    followups,
    forms,
    intake,
    interview,
    patient_checkin,
    patients,
    report,
    scheduling,
    visits,
    voice,
)
from app.services import store

app = FastAPI(
    title="PrelimMD API",
    version="0.2.0",
    description=(
        "Backend for PrelimMD — AI-assisted patient intake, self check-in, "
        "and post-discharge follow-up platform."
    ),
)

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Origins are loaded from the ALLOWED_ORIGINS environment variable.
# Defaults cover local development for both Next.js (3000) and Vite (5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Staff Portal routes ───────────────────────────────────────────────────────
app.include_router(patients.router,        prefix="/patients",   tags=["Patients"])
app.include_router(visits.router,          prefix="/visits",     tags=["Visits"])
app.include_router(intake.router,          prefix="/intake",     tags=["Intake (Staff)"])
app.include_router(followups.router,       prefix="/followups",  tags=["Follow-Ups (Staff)"])

# ── Patient Check-In routes ───────────────────────────────────────────────────
app.include_router(patient_checkin.router, prefix="/patient",    tags=["Patient Check-In"])

# ── Session / Interview orchestration ─────────────────────────────────────────
app.include_router(interview.router,       prefix="/interview",  tags=["Interview Session"])

# ── Voice (STT + TTS + voice sessions) ───────────────────────────────────────
app.include_router(voice.router,           prefix="/voice",      tags=["Voice"])

# ── Form management (AI engine) ───────────────────────────────────────────────
app.include_router(forms.router,           prefix="/forms",      tags=["Forms"])
app.include_router(calls.router,           prefix="/calls",      tags=["Calls (Legacy)"])

# ── Reports ───────────────────────────────────────────────────────────────────
app.include_router(report.router,          prefix="/report",     tags=["Report"])

# ── Scheduling (deprecated shim → see /followups) ────────────────────────────
app.include_router(scheduling.router,      prefix="/scheduling", tags=["Scheduling (Deprecated)"])

# ── Static assets (ElevenLabs TTS files for Twilio <Play>) ──────────────────
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup():
    store.init_db()


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe."""
    return {
        "status": "ok",
        "version": app.version,
        "cors_origins": settings.cors_origins,
        "elevenlabs_configured": bool(settings.elevenlabs_api_key),
        "openai_configured": bool(settings.openai_api_key),
        "deepgram_configured": bool(settings.deepgram_api_key),
        "twilio_configured": bool(
            settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_phone_number
        ),
        "database_configured": bool(settings.database_url),
        "public_base_url": settings.resolved_public_base_url or None,
    }
