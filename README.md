# PrelimMD MVP

A conversational AI voice/video agent that acts as the first step for appointment access.
It collects symptoms and context through a guided conversation, performs conservative risk
stratification and routing, offers scheduling options, and generates a clinician-facing
intake transcript plus structured summary.

---

## Project Structure

```
prelimmd/
├── frontend/       # Next.js + TypeScript UI
├── backend/        # FastAPI Python server
├── shared/         # Shared schemas/types across frontend & backend
└── docker-compose.yml
```

---

## Setup Instructions

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in DEEPGRAM_API_KEY and others
uvicorn app.main:app --reload
```

---

## Team Responsibilities

| Area       | Owner         | Key Files                                              |
|------------|---------------|--------------------------------------------------------|
| AI         | AI teammate   | `backend/app/services/ai_engine.py`, `routes/interview.py` |
| Voice      | Voice teammate| `backend/app/services/voice_service.py`, `routes/voice.py` |
| Frontend   | FE teammate   | `frontend/src/app/`, `frontend/src/components/`        |
| Report/Sched | Report teammate | `backend/app/services/report_generator.py`, `scheduler.py`, `routes/report.py`, `routes/scheduling.py` |

---

## Branching Strategy (suggested)

```
main
├── feature/ai-engine
├── feature/voice-system
├── feature/frontend-ui
└── feature/report-scheduling
```

---

## Environment Variables

Copy `.env.example` files in both `frontend/` and `backend/` and fill in real values before running.
