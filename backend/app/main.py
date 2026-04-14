# app/main.py
# FastAPI application entry point.
# Registers all routers and configures middleware.
#
# TODO: Backend - add CORS origins once frontend URL is known
# TODO: Backend - add auth middleware (JWT / API key) before going to production
# TODO: Backend - add structured logging middleware

from fastapi import FastAPI
from app.routes import interview, voice, report, scheduling

app = FastAPI(
    title="PrelimMD API",
    version="0.1.0",
    description="Backend for the PrelimMD AI pre-screening assistant",
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(interview.router, prefix="/interview", tags=["Interview"])
app.include_router(voice.router,     prefix="/voice",     tags=["Voice"])
app.include_router(report.router,    prefix="/report",    tags=["Report"])
app.include_router(scheduling.router,prefix="/scheduling",tags=["Scheduling"])


@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe — returns 200 when the server is up."""
    return {"status": "ok"}
