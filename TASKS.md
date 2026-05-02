# PrelimMD — Task Tracker

Last updated: 2026-05-02

---

## Completed (Backend Cleanup Pass)

- [x] Rewrote root README.md to match new PrelimMD product framing
- [x] Deleted unused dead file `shared/types/interview.schema.json`
- [x] Fixed CORS — added `CORSMiddleware` with environment-controlled allowed origins
- [x] Updated `config.py` — added `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ALLOWED_ORIGINS`
- [x] Updated `.env.example` — documented all required and optional env vars
- [x] Updated `requirements.txt` — added `elevenlabs`, `httpx`
- [x] Rewrote `models/schemas.py` — full data model covering all entities
- [x] Created `services/store.py` — central mock data store with 4 patients, 5 visits, 3 templates, 12 question bank items
- [x] Created `services/interview_engine.py` — intake + follow-up session orchestration with safety rules
- [x] Created `services/tts_service.py` — ElevenLabs TTS abstraction with graceful fallback
- [x] Created `routes/patients.py` — `GET /patients`, `GET /patients/{id}`
- [x] Created `routes/visits.py` — `GET /visits`, `GET /visits/{id}`, `GET /visits/{id}/forms`
- [x] Created `routes/intake.py` — staff intake workflow (assign, prefill, schedule-call, session)
- [x] Created `routes/followups.py` — follow-up task management + question bank
- [x] Created `routes/patient_checkin.py` — kiosk routes (validate, forms, submit, sign)
- [x] Implemented `routes/interview.py` — session start, answer, get, complete
- [x] Updated `routes/voice.py` — added TTS synthesize, voice intake/followup session routes
- [x] Repurposed `routes/scheduling.py` — returns 410 Gone with redirect to `/followups`
- [x] Updated `main.py` — CORS middleware + all new routers registered
- [x] Created `frontend/staff-portal/README.md` — placeholder with spec
- [x] Created `frontend/patient-checkin/README.md` — placeholder with spec
- [x] Created `TASKS.md`, `SYSTEM_STATE.md`, `MEMORY.md`
- [x] Refactored `routes/voice.py` into Twilio webhook endpoints that return TwiML
- [x] Added Twilio call-state tracking in `store.py` keyed by `CallSid`
- [x] Mounted `backend/static` for ElevenLabs MP3 playback through Twilio `<Play>`
- [x] Added optional outbound call trigger `POST /voice/call/start`
- [x] Wired follow-up phone responses into `store.save_followup_response()`
- [x] Added `backend/tools/voice_call_tester.py` Streamlit dashboard for local Twilio-flow simulation
- [x] Updated `requirements.txt` with `streamlit` and `requests` for local voice testing

---

## Backend — Remaining / In Progress

### High Priority

- [ ] **Database**: Replace in-memory store (`store.py`) with SQLite or PostgreSQL using SQLAlchemy + Alembic
- [ ] **Real FHIR/EHR**: Replace mock data in `fhir_service.py` with real OpenMRS FHIR API calls
- [ ] **Auth middleware**: Add JWT or API key auth before any production deployment
- [ ] **Voice LLM bridge**: Wire `voice_service.py::_call_llm()` to the interview engine (replace placeholder)

### Medium Priority

- [ ] **Structured logging**: Add JSON logging middleware to `main.py`
- [ ] **Error handling**: Add retry logic for OpenAI API calls (rate limits, timeouts)
- [ ] **Docker Compose**: Uncomment and configure service definitions in `docker-compose.yml`

### Low Priority

- [ ] **Form template upload**: Allow staff to upload a new PDF form template (currently only pre-seeded templates are available)
- [ ] **Visit check-in status sync**: When kiosk sign is complete, propagate status to clinical workflow system

---

## Frontend — Not Yet Started

### Staff Portal (`frontend/staff-portal/`)

- [ ] Choose framework (Next.js 14 recommended for consistency)
- [ ] Patient list view (today's schedule)
- [ ] Visit detail view with form assignment UI
- [ ] Form template selector (calls `GET /intake/templates`)
- [ ] Trigger prefill button (calls `POST /intake/prefill/{visit_id}`)
- [ ] Schedule intake call UI
- [ ] Follow-up scheduler (question bank + custom questions)
- [ ] Session/response review view (collected answers, flags)
- [ ] Clinical brief viewer (links to existing report routes)

### Patient Check-In Portal (`frontend/patient-checkin/`)

- [ ] Choose framework (Next.js or Vite/React)
- [ ] Identity verification screen (name + DOB + visit date)
- [ ] Form review screen (prefilled fields with confirm/edit)
- [ ] Missing field fill-in screen
- [ ] Consent signature screen
- [ ] Confirmation / "check-in complete" screen

---

## Telephony / ElevenLabs — Remaining

- [ ] Validate the new Streamlit tester against a live local backend session from start to finish
- [ ] Test ElevenLabs TTS with a real API key and public `PUBLIC_BASE_URL`
- [ ] Verify Twilio webhook flow end-to-end through ngrok with live speech recognition
- [ ] Improve DOB parsing beyond numeric/month-name phrases
- [ ] Wire outbound dial into `POST /intake/schedule-call` response
- [ ] Wire outbound dial into follow-up task scheduler
