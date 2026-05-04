# PrelimMD — Project Memory & Decision Log

This file records decisions, repo-state changes, and context that are not obvious from a quick code scan.

---

## 2026-05-04 — Repo Status Refresh And Frontend Validation

## 2026-05-04 — Workflow Correction For Staff Portal And Patient Check-In

## 2026-05-04 — Staff Portal Rebuild And Hydration Fix

## 2026-05-04 — DB-First Prefill And Historical Form Reuse

## 2026-05-04 — Normalized Reusable History And Patient Check-In Flow Upgrade

### What changed

- Added normalized reusable clinical tables:
  - `patient_medications`
  - `patient_allergies`
  - `patient_conditions`
  - `reusable_field_facts`
- Prefill now carries `last_confirmed_at` metadata so patient check-in can show when a value came from prior confirmation.
- Patient check-in flow was rebuilt to:
  - merge duplicate fields across multiple assigned forms
  - show all remaining fields, not just a partial subset
  - allow inline edit completion with Enter or Done
  - add per-question speaker buttons
  - add per-question microphone dictation
  - add a guided voice-fill mode for sequential conversation-style completion
  - show a final merged review before signature
- Staff portal now auto-refreshes on interval/focus for dashboard and visit views so checked-in status is visible without manual reload.

### Validation

- `backend/app`: compile passed
- `frontend/patient-checkin`: lint passed
- `frontend/patient-checkin`: build passed
- `frontend/staff-portal`: lint passed
- `frontend/staff-portal`: build passed

### What changed

- Replaced the old mock-FHIR-first prefill behavior with a DB-first deterministic prefill path.
- Prefill now searches, in order:
  - prior completed forms for the patient
  - prior intake session answers for the patient
  - current patient record in Postgres
  - current visit record in Postgres
  - optional mock clinical data only as fallback
- Added alias and label heuristics so uploaded/custom forms can still map fields like:
  - `sex` -> `gender`
  - `member id / policy number` -> `insurance_id`
  - `emergency phone` -> `emergency_contact_phone`
- Added a durable `completed_forms` table and store helpers so completed intake data survives backend restarts.
- Patient kiosk completion now writes completed form snapshots to the database and updates assignment status to `signed`.
- Historical completed forms are now reused on future visits so returning patients can often just validate and sign.

### Decisions made

- Stop treating mock FHIR/OpenMRS data as the primary source of truth for intake prefill.
- Use the app’s own Postgres data as the canonical prefill base.
- Treat prior patient-confirmed intake data as valuable history, especially for:
  - demographics
  - insurance
  - emergency contact
  - allergies
  - medications

### Validation

- `python3 -m compileall backend/app` passed

### What remains unfinished

- Medications, allergies, and conditions are still stored as reusable completed-form history, not yet as fully normalized clinical tables.
- There is still no recency/expiration policy for patient-confirmed facts, so the UI should eventually distinguish:
  - recently confirmed
  - older historical data that should be revalidated

### What changed

- Rebuilt `frontend/staff-portal` around a single consistent Tailwind-based app shell.
- Fixed the Next.js hydration/runtime break by removing nested route layouts that incorrectly rendered their own `<html><body>` trees under:
  - `src/app/patients/layout.tsx`
  - `src/app/visits/layout.tsx`
  - `src/app/followups/layout.tsx`
- Replaced the mixed old/new portal pages with DB-backed pages for:
  - dashboard
  - patients
  - visits
  - visit workspace
  - call schedule
  - forms library
  - risk alerts
  - follow-up queue/detail
- Added intake session fetching to the frontend API layer with `GET /intake/sessions`.
- Kept the patient check-in launcher and visit workflow integrated with the existing backend/Postgres flow.

### Decisions made

- Prefer one stable staff portal IA over partial nurse/doctor sub-apps:
  - nurse setup and intake prep live in dashboard/patients/visits/calls/forms-library
  - doctor review and post-visit follow-up live in risk-alerts/followups
- Use backend and DB data for portal content instead of hardcoded sample rows.
- Keep department-based form suggestions derived from stored template categories, not fixed template names.

### Validation

- `frontend/staff-portal`: `npm run lint` passed
- `frontend/staff-portal`: `npm run build` passed
- The staff portal route set now builds cleanly with:
  - `/`
  - `/patients`
  - `/visits`
  - `/visits/[id]`
  - `/calls`
  - `/forms-library`
  - `/risk-alerts`
  - `/followups`
  - `/followups/[id]`

### What remains unfinished

- The visit workspace still does not let staff edit visit department/provider after creation because there is no backend update route yet.
- Risk alert severity is still derived from stored follow-up flags; richer doctor analytics still need backend support.
- Intake session transcript review and follow-up response review are still separate follow-on tasks.

### What changed

- Corrected the intended product workflow in code and repo docs:
  - staff portal is now the nurse/doctor intake setup workspace
  - patient check-in is now the patient validation/review/consent workspace
- Added staff-side backend workflow support:
  - `POST /patients` to create patient records
  - `POST /visits` to create scheduled visits
  - `POST /intake/templates/upload` to upload or scan a PDF/image into a reusable form template stored in the database
- Updated the staff portal to support:
  - a dedicated scheduled visits tab
  - patient creation and visit scheduling from the patients tab
  - visit-level template assignment
  - visit-level PDF/photo/camera upload to create and assign new templates
  - automatic AI prefill immediately after assignment/upload
  - AI intake call scheduling from the visit workspace
- Updated patient check-in to:
  - remove the camera scan workflow from the patient side
  - focus on verification, prefilled review, missing fields, and consent
  - add a simple read-aloud helper for remaining questions
- Replaced both portal placeholder brand marks with `frontend/images/logo.png`

### Decisions made

- The camera/photo form capture belongs to staff intake preparation, not the patient kiosk.
- The nurse workflow should be visit-centric:
  - schedule patient
  - assign/upload form
  - run prefill
  - schedule AI call
  - send patient to self check-in
- Patient check-in should not ask patients to digitize clinic paperwork if staff can do that earlier in the workflow.
- For the quick accessibility improvement, use browser speech synthesis in the patient portal instead of waiting for a full voice-agent form entry implementation.

### Validation

- Backend compile: passed
- Staff portal lint: passed
- Staff portal build: passed
- Patient check-in lint: passed
- Patient check-in build: passed

### What remains unfinished

- Persist the AI engine’s parsed/prefilled/completed form caches in Postgres instead of process memory
- Add a proper staff-facing transcript/session review screen
- Add patient-side voice input, not just read-aloud assistance
- Add auth/roles
- Add Alembic migrations for managed schema evolution

### What changed

- Updated `MEMORY.md`, `SYSTEM_STATE.md`, and `TASKS.md` so they match the current codebase instead of the earlier placeholder/frontend-not-started state.
- Verified the FastAPI backend imports successfully from `backend/venv` and compiles with:
  - `venv/bin/python -c "from app.main import app; print(app.version)"`
  - `venv/bin/python -m compileall app`
- Installed frontend dependencies locally and ran TypeScript checks for both Next.js apps.
- Fixed a real patient check-in frontend type mismatch:
  - `frontend/patient-checkin/src/app/checkin/[visit_id]/page.tsx`
  - Replaced `field.needs_review` with `field.needs_confirmation` to match the backend/API model.
- Removed `next/font/google` usage from both frontend layouts and replaced it with local CSS font stacks.
- Added committed `.eslintrc.json` files for both frontend apps.
- Made the staff portal kiosk launch URL configurable with `NEXT_PUBLIC_PATIENT_CHECKIN_URL`.

### What was learned

- The repo now has two actual frontend apps, not placeholders:
  - `frontend/patient-checkin` has welcome, verify, new-patient, check-in, and complete flows.
  - `frontend/staff-portal` has dashboard, patient roster, visit detail, follow-up queue, and follow-up detail pages.
- The current local backend virtualenv path is `backend/venv`, not `backend/.venv`.
- Both frontends default to `NEXT_PUBLIC_API_URL=http://localhost:8000` if no `.env.local` is present.
- The staff portal now defaults the kiosk launch URL to `http://localhost:3001` but can override it with `NEXT_PUBLIC_PATIENT_CHECKIN_URL`.

### Validation results

- Backend import/compile: passed
- `npx tsc --noEmit`:
  - `frontend/patient-checkin`: passed after the `needs_confirmation` fix
  - `frontend/staff-portal`: passed
- `npm run lint`:
  - `frontend/patient-checkin`: passed
  - `frontend/staff-portal`: passed
- `npm run build`:
  - `frontend/patient-checkin`: passed
  - `frontend/staff-portal`: passed

### Decisions made

- Use the codebase as the source of truth for progress tracking, not the older planning docs.
- Prefer local/system font stacks for these frontends so builds do not depend on external font fetches.
- Keep a committed ESLint config in each frontend app so `next lint` is CI-safe and non-interactive.

### What remains unfinished

- Surface more backend data in the UI:
  - intake session review
  - follow-up responses
  - report/clinical brief review
- Add auth, persistence, and real FHIR/EHR integration.
- Rotate/remove live secrets from `backend/.env` and keep only safe examples in tracked docs/files.

---

## 2026-05-02 — Backend Cleanup Pass (Pivot to new product framing)

### What changed

- Product framing moved from generic conversational access tooling to:
  - AI-assisted patient intake
  - self check-in
  - post-discharge follow-up
- Backend architecture was reorganized around:
  - `store.py`
  - `interview_engine.py`
  - `patients.py`
  - `visits.py`
  - `intake.py`
  - `followups.py`
  - `patient_checkin.py`
- Root docs were introduced:
  - `TASKS.md`
  - `SYSTEM_STATE.md`
  - `MEMORY.md`

### Key decisions

- Keep MVP state in-memory until persistence becomes the immediate bottleneck.
- Preserve compatibility routes instead of deleting them when possible.
- Keep safety rules embedded in the interview engine so patient-facing flows do not drift.

### What remained unfinished at that point

- Database
- Real FHIR/EHR integration
- Auth
- Production-grade frontend apps

---

## 2026-05-02 — Twilio + ElevenLabs Voice-Call MVP

### What changed

- Added Twilio-compatible intake and follow-up voice routes returning TwiML.
- Added outbound call trigger support.
- Added ElevenLabs audio generation with `/static/tts/...` playback fallback behavior.
- Added `VoiceCallSession` state keyed by `CallSid`.

### Key decisions

- Keep telephony control deterministic inside `routes/voice.py`.
- Reuse the existing in-memory store pattern for telephony state.
- Serve synthesized audio directly from FastAPI static files.

### What remained unfinished at that point

- Live end-to-end Twilio verification
- Stronger DOB parsing
- Persistence across restarts
- Automatic dial launch from staff scheduling actions

---

## 2026-05-02 — Local Streamlit Voice Call Tester

### What changed

- Added `backend/tools/voice_call_tester.py`.
- Added a local Twilio-style simulation path for the current `/voice/*` routes.

### Key decisions

- Test the production-style voice webhooks directly rather than inventing a second test-only flow.
- Keep the tool lightweight and local to the backend developer workflow.

### What remained unfinished at that point

- Manual validation still depends on a running backend and realistic seeded data.
- Real live-call verification still needs Twilio/ngrok.

---

## Template For Future Entries

```md
## YYYY-MM-DD — Short Title

### What changed
- File/feature changes

### What was learned
- Repo or behavior observations

### Decisions made
- Chosen approach and rationale

### What remains unfinished
- Open work and blockers
```
