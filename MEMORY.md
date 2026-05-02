# PrelimMD — Project Memory & Decision Log

This file records important decisions, changes, and context that aren't obvious from the code.
Update this whenever a significant decision is made or direction changes.

---

## 2026-05-02 — Backend Cleanup Pass (Pivot to new product framing)

### What changed

**Product pivot:**
- Old framing: "conversational AI voice/video agent for appointment access"
- New framing: AI-assisted patient intake, self check-in, and post-discharge follow-up platform
- Two future frontend experiences: Staff Portal (nurses/doctors) and Patient Self Check-In (kiosk)

**Files deleted:**
- `shared/types/interview.schema.json` — unused JSON schema file, never imported by Python or JS code

**Files created:**
- `backend/app/services/store.py` — central in-memory mock data store (replaces scattered in-memory dicts)
- `backend/app/services/interview_engine.py` — reusable session orchestration for both intake and follow-up
- `backend/app/services/tts_service.py` — ElevenLabs TTS abstraction with graceful fallback to text
- `backend/app/routes/patients.py` — patient lookup
- `backend/app/routes/visits.py` — scheduled visit lookup
- `backend/app/routes/intake.py` — staff intake workflow (assign, prefill, schedule)
- `backend/app/routes/followups.py` — post-discharge follow-up management
- `backend/app/routes/patient_checkin.py` — kiosk self check-in flow
- `frontend/staff-portal/README.md` — placeholder spec for Staff Portal
- `frontend/patient-checkin/README.md` — placeholder spec for Patient Check-In
- `TASKS.md`, `SYSTEM_STATE.md`, `MEMORY.md`

**Files modified:**
- `backend/app/main.py` — added CORS middleware, registered all new routers
- `backend/app/config.py` — added `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ALLOWED_ORIGINS`, `cors_origins` property
- `backend/app/models/schemas.py` — full rewrite adding: `Patient`, `ScheduledVisit`, `StaffUser`, `FormTemplate`, `AssignedForm`, `IntakeCallSession`, `SessionTurn`, `PostDischargeFollowUpTask`, `FollowUpQuestion`, `FollowUpResponse`, all check-in models, voice models; legacy models kept
- `backend/app/routes/interview.py` — implemented (was empty TODO stubs)
- `backend/app/routes/voice.py` — added `/voice/synthesize`, `/voice/intake/start`, `/voice/intake/answer`, `/voice/followup/start`, `/voice/followup/answer`
- `backend/app/routes/scheduling.py` — repurposed; now returns 410 Gone with redirect to `/followups`
- `backend/.env.example` — updated to include all variables
- `backend/requirements.txt` — added `elevenlabs`, `httpx`
- `README.md` — full rewrite

### Why decisions were made

**In-memory store instead of SQLite:**
The existing `ai_engine.py` already used in-memory dicts. Adding SQLite would require SQLAlchemy, migrations, and more setup. Since we're at MVP stage with no persistence requirement yet, centralizing all mock data in `store.py` is a better intermediate step. When ready, the store functions can be swapped out for real DB calls without changing the routes.

**ElevenLabs as TTS abstraction:**
The `.env.example` already had `ELEVENLABS_API_KEY` from a previous setup. ElevenLabs was the intended provider. The service is designed to fail gracefully (returns `None` → text fallback) so the backend never crashes if the key is missing.

**`/scheduling` → 410 Gone instead of deletion:**
Deleted the stubs but kept the router file and prefix to avoid breaking any existing clients or postman collections. The 410 response explains where to go.

**Safety rules in interview_engine.py:**
Hard-coded as system prompt instructions. These cannot be overridden by user input since they're applied at every LLM call within the engine. If a patient asks for medical advice, the model is instructed to redirect — not answer.

### What remains unfinished

- Database (all state is in-memory, lost on restart)
- Real FHIR/EHR API calls (currently mock data in `fhir_service.py`)
- Auth middleware (JWT/API key)
- Outbound calling (Twilio/ElevenLabs dial)
- Both frontend UIs
- ElevenLabs TTS real-key testing

---

## 2026-05-02 — Twilio + ElevenLabs voice-call MVP

### What changed

**Files modified:**
- `backend/app/routes/voice.py`
- `backend/app/services/store.py`
- `backend/app/models/schemas.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/.env.example`
- `README.md`
- `TASKS.md`
- `SYSTEM_STATE.md`
- `MEMORY.md`

**Voice endpoints now return TwiML for phone calls:**
- `GET|POST /voice/intake/start` starts or attaches to an intake session and returns TwiML with a speech `<Gather>`
- `POST /voice/intake/answer` consumes Twilio `SpeechResult`, stores answers, advances the intake flow, and returns the next TwiML
- `GET|POST /voice/followup/start` starts or attaches to a follow-up session and returns TwiML
- `POST /voice/followup/answer` stores doctor-selected follow-up answers and flags concerning responses
- `POST /voice/call/start` optionally queues an outbound Twilio call if Twilio credentials are configured
- `GET /voice/test-twiml` returns sample XML for quick verification

**ElevenLabs fallback behavior:**
- If `ELEVENLABS_API_KEY` and `PUBLIC_BASE_URL` are available, TTS audio is written to `backend/static/tts/` and Twilio receives `<Play>` URLs
- If ElevenLabs is missing, fails, or there is no public base URL, the system falls back to Twilio `<Say>`

**CallSid mapping:**
- Added `VoiceCallSession` state in `store.py`
- Each Twilio `CallSid` maps to:
  - `session_id`
  - `mode` (`intake` or `followup`)
  - `patient_id`
  - `visit_id` or `task_id`
  - verification state and attempt counters
  - current question index
  - retry/unclear/clarification counters
  - completion status/reason

### Decisions made

**Deterministic Twilio loop instead of LLM-driven call control:**
- The existing `interview_engine.py` is still used to create intake/follow-up sessions
- Actual Twilio phone progression is handled deterministically inside `routes/voice.py`
- Reason: the phone-call loop needs reliable verification, retries, hangups, and Twilio form handling even when LLM output is unavailable or too loose for telephony control flow

**Keep storage consistent with current MVP:**
- The repo still uses the existing mock/in-memory store pattern
- Added a small `VoiceCallSession` collection in `store.py` rather than introducing a new database layer

**Static audio served from FastAPI:**
- `main.py` now mounts `/static`
- This keeps ElevenLabs output accessible to Twilio over ngrok/public HTTPS without adding a separate storage service

### What remains unfinished

- End-to-end live Twilio verification through ngrok still needs a real phone call test
- DOB parsing is practical but limited to common numeric and month-name phrases
- Call/session state is still in-memory and resets on server restart
- `POST /intake/schedule-call` and `POST /followups/schedule` do not yet auto-trigger outbound dialing

---

## 2026-05-02 — Local Streamlit voice call tester

### What changed

**Files modified:**
- `backend/tools/voice_call_tester.py`
- `backend/requirements.txt`
- `README.md`
- `TASKS.md`
- `SYSTEM_STATE.md`
- `MEMORY.md`

**Tester behavior:**
- Added a local Streamlit developer dashboard at `backend/tools/voice_call_tester.py`
- The tool simulates Twilio by POSTing form data to:
  - `/voice/intake/start`
  - `/voice/intake/answer`
  - `/voice/followup/start`
  - `/voice/followup/answer`
- It sends fake `CallSid`, `From`, `To`, `SpeechResult`, and `Confidence` fields
- It parses TwiML to extract:
  - `<Say>` text
  - `<Play>` URL
  - `<Gather action>`
  - `<Redirect>`
  - `<Hangup>`
- It keeps local conversation history and can optionally inspect `GET /interview/session/{session_id}`

### Decisions made

**No backend call-flow changes for the tester:**
- The tester consumes the existing production Twilio-style endpoints as-is
- Reason: the goal is to validate the current webhook/TwiML loop, not create a second voice implementation

**Streamlit instead of a browser frontend app:**
- The tester is a single local Python file with no production routing implications
- Reason: this keeps the tool fast to run for backend developers and avoids introducing a real frontend stack

**`requests` + XML parsing only:**
- The tester uses `requests` and `xml.etree.ElementTree`
- Reason: minimal dependencies and direct visibility into the raw TwiML returned by the backend

### What remains unfinished

- The tester still depends on a locally running FastAPI backend with the relevant mock/prepared data
- If a call is started from `visit_id` or `followup_id` instead of a known `session_id`, session inspection depends on the developer already knowing which session to inspect
- Live manual verification in Streamlit still needs to be run in the project virtualenv

---

## Template for future entries

```
## YYYY-MM-DD — [Short title]

### What changed
- File X was created/modified/deleted
- Why: [reason]

### Decisions made
- [Decision]: [rationale]

### What remains unfinished
- [items]
```
