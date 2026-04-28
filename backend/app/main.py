# app/main.py
# FastAPI application entry point.
# Registers all routers and configures middleware.
#
# TODO: Backend - add auth middleware (JWT / API key) before going to production
# TODO: Backend - add structured logging middleware

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import forms, interview, voice, report, scheduling

app = FastAPI(
    title="PrelimMD API",
    version="0.1.0",
    description="Backend for the PrelimMD AI pre-screening assistant",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(interview.router, prefix="/interview", tags=["Interview"])
app.include_router(forms.router,     prefix="/forms",     tags=["Forms"])
app.include_router(voice.router,     prefix="/voice",     tags=["Voice"])
app.include_router(report.router,    prefix="/report",    tags=["Report"])
app.include_router(scheduling.router,prefix="/scheduling",tags=["Scheduling"])


@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe — returns 200 when the server is up."""
    return {"status": "ok"}
