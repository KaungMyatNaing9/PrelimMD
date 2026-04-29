from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import interview, voice, report, scheduling

app = FastAPI(
    title="PrelimMD API",
    version="1.0.0",
    description="AI-powered pre-visit medical interview system",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interview.router,   prefix="/interview",   tags=["Interview"])
app.include_router(voice.router,       prefix="/voice",       tags=["Voice"])
app.include_router(report.router,      prefix="/report",      tags=["Report"])
app.include_router(scheduling.router,  prefix="/scheduling",  tags=["Scheduling"])


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
