# PrelimMD — Backend

FastAPI application (Python 3.10+).

## Getting Started

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in DEEPGRAM_API_KEY and others
uvicorn app.main:app --reload   # http://localhost:8000
```

Interactive API docs: http://localhost:8000/docs

## Voice / STT Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/voice/transcribe` | POST | Upload an audio/video file, get back transcript JSON |
| `/voice/stream` | WebSocket | Stream mic audio, receive live transcripts on each pause |

To test live streaming in the browser: `python3 -m http.server 8080` then open `http://localhost:8080/test_stream.html`.

See the comment block at the top of `app/routes/voice.py` for the full frontend integration spec.

## Key Directories

| Path | Purpose |
|---|---|
| `app/main.py` | App entry point, router registration |
| `app/config.py` | Typed settings loaded from `.env` |
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
