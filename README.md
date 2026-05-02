# PrelimMD

AI-assisted patient intake, self check-in, and post-discharge follow-up platform.

PrelimMD streamlines clinical workflows by combining staff-guided form selection with intelligent EHR-based prefill, targeted patient question collection (via call or kiosk), and doctor-configured post-discharge follow-up calls.

---

## How It Works

### Pre-Visit Intake
1. **Staff assigns forms** — nurses/doctors select which intake forms a patient needs for their scheduled visit
2. **EHR prefill** — the system automatically fills known fields from existing patient records (mock EHR for MVP)
3. **Missing field collection** — remaining fields are collected via a pre-visit phone call (AI-driven) or at the kiosk on arrival
4. **Intake call** — an AI agent calls the patient, asks only the missing questions, and stores answers

### Patient Self Check-In (Kiosk)
1. Patient verifies identity (name + DOB + visit date)
2. Patient reviews prefilled form fields, corrects any errors, and completes missing fields
3. Patient signs consent electronically
4. Staff receives the completed, reviewed form

### Post-Discharge Follow-Up
1. **Staff configures follow-up** — doctor selects standard questions from a question bank and optionally adds custom questions
2. **AI agent calls patient** — conducts a structured follow-up call at the scheduled time
3. **Risk flagging** — concerning answers (worsening symptoms, medication non-adherence) are flagged for the care team
4. **Staff reviews** — results are visible in the Staff Portal

---

## Project Structure

```
PrelimMD/
├── backend/                   # FastAPI Python API server (primary focus for now)
│   ├── app/
│   │   ├── main.py            # App entry point, CORS, router registration
│   │   ├── config.py          # Typed settings loaded from .env
│   │   ├── models/
│   │   │   └── schemas.py     # All Pydantic data models
│   │   ├── routes/            # HTTP endpoint handlers
│   │   │   ├── patients.py         # GET /patients, GET /patients/{id}
│   │   │   ├── visits.py           # GET /visits, GET /visits/{id}
│   │   │   ├── intake.py           # Staff intake workflow (assign, prefill, schedule)
│   │   │   ├── followups.py        # Post-discharge follow-up management
│   │   │   ├── patient_checkin.py  # Patient kiosk routes (validate, review, sign)
│   │   │   ├── interview.py        # Session orchestration (start, answer, complete)
│   │   │   ├── voice.py            # STT (Deepgram) + TTS (ElevenLabs) + voice sessions
│   │   │   ├── forms.py            # Form upload, OCR parsing, prefill (legacy AI engine)
│   │   │   ├── calls.py            # Legacy call flow (kept for compatibility)
│   │   │   └── report.py           # Clinical brief + PDF report
│   │   └── services/          # Business logic
│   │       ├── store.py            # Central mock data store (patients, visits, tasks)
│   │       ├── interview_engine.py # Intake + follow-up session orchestration
│   │       ├── tts_service.py      # ElevenLabs TTS abstraction with fallback
│   │       ├── ai_engine.py        # Form parsing, EHR diff, clinical brief (LLM agents)
│   │       ├── fhir_service.py     # Mock EHR patient data (replace with real FHIR later)
│   │       └── voice_service.py    # Deepgram STT integration
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                  # Frontend placeholder — UIs not yet implemented
│   ├── staff-portal/
│   │   └── README.md          # Staff Portal spec (nurses/doctors)
│   └── patient-checkin/
│       └── README.md          # Patient Self Check-In spec (kiosk)
│
├── TASKS.md                   # Task tracking
├── SYSTEM_STATE.md            # Current architecture and API reference
└── MEMORY.md                  # Change log and decision record
```

---

## Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # fill in API keys
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs: **http://localhost:8000/docs**

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | GPT-4o for form parsing, prefill agent, clinical brief |
| `DEEPGRAM_API_KEY` | For voice | Speech-to-text transcription |
| `ELEVENLABS_API_KEY` | Optional | Text-to-speech; falls back to text if not set |
| `ELEVENLABS_VOICE_ID` | Optional | ElevenLabs voice ID (default: Rachel) |
| `PUBLIC_BASE_URL` | For Twilio/Play | Public HTTPS base URL Twilio can reach, e.g. ngrok |
| `BACKEND_PUBLIC_URL` | Optional fallback | Alternate name for `PUBLIC_BASE_URL` |
| `TWILIO_ACCOUNT_SID` | For outbound calls | Twilio REST API account SID |
| `TWILIO_AUTH_TOKEN` | For outbound calls | Twilio REST API auth token |
| `TWILIO_PHONE_NUMBER` | For outbound calls | Twilio number used as the caller ID |
| `ALLOWED_ORIGINS` | Optional | Comma-separated CORS origins (defaults to localhost:3000 + 5173) |

---

## API Overview

### Staff Portal APIs
| Method | Path | Description |
|---|---|---|
| GET | `/patients` | List all patients |
| GET | `/patients/{id}` | Get a single patient |
| GET | `/visits` | List visits (filter by `?patient_id=`) |
| GET | `/visits/{id}` | Get a single visit |
| GET | `/visits/{id}/forms` | Get forms assigned to a visit |
| GET | `/intake/templates` | List available form templates |
| POST | `/intake/assign` | Assign a form template to a visit |
| POST | `/intake/prefill/{visit_id}` | Run EHR prefill for all assigned forms |
| POST | `/intake/schedule-call` | Record that an intake call is scheduled |
| GET | `/intake/session/{session_id}` | Review a completed intake session |
| GET | `/followups/question-bank` | Browse standard follow-up questions |
| POST | `/followups/schedule` | Schedule a post-discharge follow-up call |
| GET | `/followups` | List all follow-up tasks |
| GET | `/followups/{id}` | Get a follow-up task with status and flags |

### Patient Check-In APIs
| Method | Path | Description |
|---|---|---|
| POST | `/patient/validate` | Verify identity (name + DOB + visit date) |
| GET | `/patient/checkin/{visit_id}/forms` | Get prefilled forms with missing fields highlighted |
| POST | `/patient/checkin/{visit_id}/submit` | Save patient's answers and corrections |
| POST | `/patient/checkin/{visit_id}/sign` | Record consent signature, mark visit checked in |

### Session / Interview APIs
| Method | Path | Description |
|---|---|---|
| POST | `/interview/start` | Start intake or follow-up session |
| POST | `/interview/answer` | Submit patient answer, get next question |
| GET | `/interview/session/{id}` | Get full session with conversation and answers |
| POST | `/interview/complete` | Close a session |

### Voice APIs
| Method | Path | Description |
|---|---|---|
| POST | `/voice/transcribe` | Upload audio file → transcript |
| WS | `/voice/stream` | Live WebSocket STT streaming |
| POST | `/voice/synthesize` | Text → MP3 audio (ElevenLabs) |
| GET/POST | `/voice/intake/start` | Twilio webhook: start intake call, verify patient, return TwiML |
| POST | `/voice/intake/answer` | Twilio webhook: process intake `SpeechResult`, return next TwiML |
| GET/POST | `/voice/followup/start` | Twilio webhook: start follow-up call, verify patient, return TwiML |
| POST | `/voice/followup/answer` | Twilio webhook: process follow-up `SpeechResult`, return next TwiML |
| POST | `/voice/call/start` | Optional outbound call trigger via Twilio REST API |
| GET | `/voice/test-twiml` | Sample TwiML health/test response |

---

## Frontend Integration Notes

Two separate frontends are planned but **not yet implemented**:

**Staff Portal** (`frontend/staff-portal/`) — for nurses and doctors to manage patient intake and follow-up. Will run on `http://localhost:3000`.

**Patient Check-In** (`frontend/patient-checkin/`) — kiosk/device interface for self check-in. Will run on `http://localhost:5173` or `3001`.

Both origins are already in the CORS allowlist. See the README inside each placeholder folder for the detailed spec.

---

## Mock Data

The backend uses in-memory mock data (loaded from `app/services/store.py`):

- **4 patients**: Jane Smith, Robert Johnson, Maria Garcia, David Kim
- **5 scheduled visits** across the patient roster
- **3 staff users**: Dr. Sarah Chen, Nurse Michael Torres, Dr. James Williams, Nurse Priya Patel
- **3 form templates**: General Intake, Cardiology Pre-Visit, Post-Op Follow-Up
- **4 form assignments** (templates linked to visits)
- **12 standard follow-up questions** across symptom, medication, mood, and activity categories
- **1 seeded follow-up task** for Jane Smith (task-001)

---

## AI Safety Rules

The interview engine enforces these rules in all patient interactions:

- Never diagnose or suggest a diagnosis
- Never recommend, start, stop, or change medications
- Never interpret lab results clinically
- If patient asks medical advice → *"I can't provide medical advice, but I can pass this to your care team."*
- If concerning symptoms mentioned → flag the session and respond: *"Thank you for telling me. I'll make sure your care team sees this right away."*

---

## Twilio Voice Setup

1. Start the backend:

```bash
cd backend
uvicorn app.main:app --reload
```

2. Expose it publicly with ngrok:

```bash
ngrok http 8000
```

3. Set the public URL in `backend/.env`:

```bash
PUBLIC_BASE_URL=https://xxxx.ngrok-free.app
```

4. In Twilio Voice webhook settings, point your number to one of:

- Intake inbound demo: `https://xxxx.ngrok-free.app/voice/intake/start?session_id=sess-...`
- Intake from visit ID: `https://xxxx.ngrok-free.app/voice/intake/start?visit_id=visit-001`
- Follow-up inbound demo: `https://xxxx.ngrok-free.app/voice/followup/start?session_id=sess-...`
- Follow-up from task ID: `https://xxxx.ngrok-free.app/voice/followup/start?task_id=task-001`

Use HTTP `POST`.

### ElevenLabs + Twilio `<Play>`

- If `ELEVENLABS_API_KEY` is configured and `PUBLIC_BASE_URL` is set, the backend writes MP3 files to `backend/static/tts/` and TwiML uses `<Play>{PUBLIC_BASE_URL}/static/tts/...mp3</Play>`.
- If ElevenLabs is missing or audio cannot be generated, the backend falls back automatically to Twilio `<Say>`.

### Inbound Call Test

1. Make sure the visit already has assigned forms and prefill/missing questions prepared.
2. Point Twilio to `/voice/intake/start?...` or `/voice/followup/start?...`.
3. Call the Twilio number.
4. The call will ask for full name, then date of birth, then continue through intake missing fields or follow-up questions.
5. Review stored answers in:
   - `GET /interview/session/{session_id}`
   - `GET /followups/{task_id}`
   - `GET /followups/{task_id}/responses`

### Local Voice Call Tester

For local development, you can simulate the Twilio call loop without Twilio credentials, real phone numbers, or ElevenLabs.

Run the backend:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run the Streamlit tester:

```bash
cd backend
streamlit run tools/voice_call_tester.py
```

What the tester does:

- Calls `/voice/intake/start`, `/voice/intake/answer`, `/voice/followup/start`, and `/voice/followup/answer` using Twilio-style form data
- Lets you choose `intake` or `followup`
- Lets you set `visit_id`, `followup_id`, optional `session_id`, and a fake `CallSid`
- Shows raw TwiML plus parsed `<Say>`, `<Play>`, `<Gather action>`, `<Redirect>`, and `<Hangup>`
- Lets you send manual `SpeechResult` text or use preset buttons for no-speech, unclear, refusal, and concerning-symptom cases
- Optionally fetches `GET /interview/session/{session_id}` when a known session ID is available

Recommended local intake test:

1. Use `visit_id=visit-001`
2. Click `Start Call`
3. Reply `Jane Smith`
4. Reply `March 14 1985`
5. Continue through the remaining prompts

This tester is strictly for local developer validation. It does not place real phone calls and it works with the backend's Twilio `<Say>` fallback.

### Outbound Call Test

If Twilio credentials are configured, you can queue an outbound call:

```bash
curl -X POST http://localhost:8000/voice/call/start \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "followup",
    "session_id": "sess-12345678",
    "to_phone": "+13125550123"
  }'
```

The session must already exist and match the requested mode.
