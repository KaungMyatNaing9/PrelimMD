# PrelimMD — Backend

FastAPI application (Python 3.10+).

## Getting Started

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in values
uvicorn app.main:app --reload   # http://localhost:8000
```

Interactive API docs: http://localhost:8000/docs

## Key Directories

| Path | Purpose |
|---|---|
| `app/main.py` | App entry point, router registration |
| `app/routes/` | HTTP route handlers (thin — delegate to services) |
| `app/services/` | Business logic (AI, voice, report, scheduler) |
| `app/models/schemas.py` | Pydantic request/response models |
| `app/utils/` | Shared helpers (logging, config, etc.) |

## Owners

| File | Team |
|---|---|
| `routes/interview.py`, `services/ai_engine.py` | AI |
| `routes/voice.py`, `services/voice_service.py` | Voice |
| `routes/report.py`, `routes/scheduling.py`, `services/report_generator.py`, `services/scheduler.py` | Report/Scheduling |
