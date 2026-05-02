# PrelimMD — System State

Last updated: 2026-05-02

---

## Architecture Overview

```
                        ┌──────────────────────┐
                        │     Staff Portal      │  (not built yet)
                        │  frontend/staff-portal│
                        └─────────┬────────────┘
                                  │ HTTP (localhost:3000)
                        ┌─────────▼────────────┐
                        │   FastAPI Backend     │
                        │  localhost:8000       │
                        │                      │
                        │  ┌────────────────┐  │
                        │  │  store.py      │  │  ← Mock in-memory DB
                        │  │  (patients,    │  │
                        │  │   visits,      │  │
                        │  │   sessions,    │  │
                        │  │   tasks)       │  │
                        │  └────────────────┘  │
                        │  ┌────────────────┐  │
                        │  │ interview_     │  │  ← Session orchestration
                        │  │ engine.py      │  │
                        │  └────────────────┘  │
                        │  ┌────────────────┐  │
                        │  │  ai_engine.py  │  │  ← Form parsing + EHR diff
                        │  └────────────────┘  │
                        │  ┌────────────────┐  │
                        │  │  tts_service   │  │  ← ElevenLabs TTS (graceful fallback)
                        │  └────────────────┘  │
                        │  ┌────────────────┐  │
                        │  │ voice.py       │  │  ← Twilio webhook + TwiML call loop
                        │  └────────────────┘  │
                        │  ┌────────────────┐  │
                        │  │ tools/voice_   │  │  ← Local Streamlit Twilio simulator
                        │  │ call_tester.py │  │
                        │  └────────────────┘  │
                        └─────────┬────────────┘
                                  │ HTTP (localhost:5173 or 3001)
                        ┌─────────▼────────────┐
                        │  Patient Check-In     │  (not built yet)
                        │  frontend/patient-    │
                        │  checkin/             │
                        └──────────────────────┘
```

**External APIs used:**
- OpenAI GPT-4o — form parsing, EHR diff agent, clinical brief generation
- Deepgram — speech-to-text transcription
- ElevenLabs — text-to-speech (optional; fallback to text if not configured)
- Twilio — voice webhooks, speech gather, optional outbound call initiation

---

## Working Endpoints

### Health
```
GET  /health         → service status, config flags
```

### Staff Portal
```
GET  /patients                          → list all patients
GET  /patients/{patient_id}             → single patient

GET  /visits                            → list visits (?patient_id= filter)
GET  /visits/{visit_id}                 → single visit
GET  /visits/{visit_id}/forms           → forms assigned to this visit

GET  /intake/templates                  → all available form templates
POST /intake/assign                     → assign form template to visit
POST /intake/prefill/{visit_id}         → run EHR diff on all assigned forms
POST /intake/schedule-call              → record intake call as scheduled
GET  /intake/session/{session_id}       → review completed intake session

GET  /followups/question-bank           → browse standard follow-up questions
POST /followups/schedule                → schedule a post-discharge follow-up
GET  /followups                         → list follow-up tasks (?patient_id= filter)
GET  /followups/{task_id}               → single follow-up task
GET  /followups/{task_id}/responses     → collected responses for a task
```

### Patient Check-In
```
POST /patient/validate                          → verify patient identity
GET  /patient/checkin/{visit_id}/forms          → get prefilled forms
POST /patient/checkin/{visit_id}/submit         → save patient answers
POST /patient/checkin/{visit_id}/sign           → record consent, mark checked in
```

### Session Orchestration
```
POST /interview/start                   → create intake or followup session
POST /interview/answer                  → submit patient answer, get next question
GET  /interview/session/{session_id}    → full session with conversation
POST /interview/complete                → close session
```

### Voice
```
POST /voice/transcribe                  → audio file → transcript (Deepgram)
WS   /voice/stream                      → live WebSocket STT streaming
POST /voice/synthesize                  → text → MP3 audio (ElevenLabs)
GET  /voice/test-twiml                  → sample XML/TwiML response
GET|POST /voice/intake/start            → Twilio intake start webhook, asks for patient name
POST /voice/intake/answer               → Twilio intake answer webhook, verifies DOB, stores answers
GET|POST /voice/followup/start          → Twilio follow-up start webhook
POST /voice/followup/answer             → Twilio follow-up answer webhook
POST /voice/call/start                  → optional outbound call via Twilio REST API
```

### Local Developer Tool
```
streamlit run backend/tools/voice_call_tester.py
```
Simulates Twilio-style call starts and answers against the existing `/voice/*` routes.

### Legacy (kept for compatibility)
```
POST /forms/upload                      → upload and OCR-parse a form PDF
GET  /forms/{form_id}/schema            → get parsed form schema
POST /forms/{form_id}/prefill           → run EHR diff on a specific form
POST /forms/{form_id}/submit            → submit call responses
GET  /forms/{form_id}/completed         → get completed form
GET  /calls/{call_id}/questions         → get compound call questions
POST /calls/{call_id}/next-question     → get adaptive next question
POST /calls/{call_id}/responses         → submit call responses
GET  /report/{form_id}                  → clinical brief JSON
GET  /report/{form_id}/pdf              → download clinical brief PDF
```

---

## Mock Data (in `services/store.py`)

### Patients
| ID | Name | DOB |
|---|---|---|
| patient-001 | Jane Smith | 1985-03-14 |
| patient-002 | Robert Johnson | 1972-07-22 |
| patient-003 | Maria Garcia | 1990-11-05 |
| patient-004 | David Kim | 1968-09-30 |

### Scheduled Visits
| ID | Patient | Date | Status |
|---|---|---|---|
| visit-001 | Jane Smith | 2026-05-05 | scheduled |
| visit-002 | Jane Smith | 2026-03-15 | completed |
| visit-003 | Robert Johnson | 2026-05-06 | scheduled |
| visit-004 | Maria Garcia | 2026-05-07 | scheduled |
| visit-005 | David Kim | 2026-05-08 | scheduled |

### Form Templates
| ID | Name | Category |
|---|---|---|
| template-001 | General Intake Form | general_intake |
| template-002 | Cardiology Pre-Visit Form | cardiology |
| template-003 | Post-Op Follow-Up Assessment | post_op |

### Assigned Forms
| ID | Visit | Template |
|---|---|---|
| assign-001 | visit-001 (Jane, Cardiology) | template-002 (Cardiology) |
| assign-002 | visit-003 (Robert, GP) | template-001 (General) |
| assign-003 | visit-004 (Maria, GP post-op) | template-003 (Post-Op) |
| assign-004 | visit-005 (David, Cardiology) | template-002 (Cardiology) |

### Question Bank
12 standard follow-up questions across categories:
`symptoms`, `medication`, `mood`, `activity`

IDs: `qb-001` through `qb-012`

### Seeded Follow-Up Task
| ID | Patient | Visit | Status |
|---|---|---|---|
| task-001 | Jane Smith (patient-001) | visit-002 | scheduled |

---

## Current Limitations

1. **All state is in-memory** — restarting the server clears sessions, follow-up results, and kiosk answers. Data seeded in `store.py` is always re-initialized on startup.
2. **No auth** — all endpoints are open. JWT/API key auth must be added before any staging/production deployment.
3. **No real EHR** — `fhir_service.py` returns hardcoded mock patient data.
4. **Twilio state is still mock-store based** — `CallSid` mappings are kept in `store.py`, so active calls are lost on restart.
5. **ElevenLabs `<Play>` requires a public URL** — without `PUBLIC_BASE_URL`/ngrok, voice calls fall back to Twilio `<Say>`.
6. **DOB parsing is MVP-level** — common numeric and month-name phrases work; more natural spoken DOB variants are not fully normalized yet.
7. **Interview/session creation still assumes prior setup** — intake calls work best after forms are assigned and prefill has generated missing fields.
8. **Form prefill requires OpenAI key** — `ai_engine.py` calls GPT-4o for EHR diff and question generation.

---

## Voice Architecture

### Phone-call flow

1. Twilio hits `/voice/intake/start` or `/voice/followup/start`
2. Backend resolves or creates an existing interview session
3. Backend creates a `VoiceCallSession` keyed by Twilio `CallSid`
4. TwiML returns a speech `<Gather>` asking for name, then DOB
5. After verification:
   - intake mode asks only remaining missing fields from assigned/prefilled forms
   - follow-up mode asks scheduled question-bank/custom follow-up questions
6. Each answer is stored in `IntakeCallSession.collected_answers`
7. Follow-up answers are also persisted as `FollowUpResponse`
8. Concerning or medical-advice-seeking answers are flagged
9. The call ends with TwiML `<Hangup>`

### Audio behavior

- Preferred path: ElevenLabs synthesizes audio, FastAPI serves it at `/static/tts/...`, and Twilio uses `<Play>`
- Fallback path: Twilio uses `<Say>` when ElevenLabs or a public base URL is unavailable

### Local testing path

1. Developer runs FastAPI locally on `http://localhost:8000`
2. Developer runs `streamlit run tools/voice_call_tester.py` from `backend/`
3. The tester sends Twilio-style form POSTs with fake `CallSid`, `From`, `To`, `SpeechResult`, and `Confidence`
4. The tester parses returned TwiML and shows:
   - raw XML
   - `<Say>` text
   - `<Play>` URL
   - `<Gather action>`
   - `<Redirect>`
   - `<Hangup>`
5. The tester can optionally query `GET /interview/session/{session_id}` for current session state when a known session ID is available

---

## Future Frontend Folder Plan

```
frontend/
├── staff-portal/          ← Staff Portal (nurses/doctors)
│   └── README.md          ← spec (complete)
└── patient-checkin/       ← Patient Self Check-In (kiosk)
    └── README.md          ← spec (complete)
```

Both portals will be built as separate React/Next.js apps that consume the FastAPI backend.
CORS is already configured to accept requests from `localhost:3000`, `localhost:5173`, and `localhost:3001`.
