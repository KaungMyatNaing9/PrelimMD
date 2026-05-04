# PrelimMD — Task Tracker

Last updated: 2026-05-04

---

## Completed

### Core backend

- [x] FastAPI app structure consolidated under `backend/app/`
- [x] CORS configured for local frontend origins including `:3000` and `:3001`
- [x] Store consolidated in `backend/app/services/store.py`
- [x] Patients, visits, intake, patient-checkin, interview, follow-up, voice, forms, report routes present
- [x] Intake overview endpoint implemented: `GET /intake/overview/{visit_id}`
- [x] New patient kiosk intake endpoint implemented: `POST /patient/new-checkin`
- [x] Kiosk scan endpoint implemented: `POST /patient/checkin/{visit_id}/scan`
- [x] Voice/Twilio routes implemented for intake and follow-up flows
- [x] Postgres-backed persistence implemented for core workflow data
- [x] Completed intake forms persisted to Postgres for future reuse
- [x] Normalized reusable patient history tables added for medications, allergies, and conditions

### Frontend implementation

- [x] Staff Portal app exists in `frontend/staff-portal`
- [x] Patient Check-In app exists in `frontend/patient-checkin`
- [x] Staff dashboard page implemented
- [x] Staff patient roster page implemented
- [x] Staff visit queue page implemented
- [x] Staff visit workflow page implemented
- [x] Staff call schedule page implemented
- [x] Staff forms library page implemented
- [x] Staff risk alerts page implemented
- [x] Staff follow-up list/detail pages implemented
- [x] Returning-patient verification flow implemented
- [x] New-patient profile creation flow implemented
- [x] Check-in review / missing fields / consent flow implemented
- [x] Staff-side PDF/photo/camera template upload flow implemented
- [x] Staff-side patient creation flow implemented
- [x] Staff-side visit scheduling flow implemented
- [x] Auto-prefill after template assignment/upload implemented
- [x] DB-first prefill implemented with prior completed-form reuse
- [x] Patient-side read-aloud helper implemented
- [x] Patient-side microphone dictation implemented
- [x] Patient-side guided voice-fill mode implemented
- [x] Patient-side deduped final review before signature implemented
- [x] Both frontends updated to use `frontend/images/logo.png`
- [x] Staff portal rebuilt to remove hydration/runtime issues from nested layouts

### Validation and repo hygiene

- [x] Backend import check passed from `backend/venv`
- [x] Backend Python compile pass completed
- [x] TypeScript checks pass for both frontends
- [x] Fixed patient check-in type mismatch:
  - `needs_review` -> `needs_confirmation`
- [x] Removed `next/font/google` dependency so both frontends build without external font fetches
- [x] Added committed ESLint config for both frontends
- [x] Made the staff portal kiosk URL configurable via `NEXT_PUBLIC_PATIENT_CHECKIN_URL`
- [x] Updated `MEMORY.md`, `SYSTEM_STATE.md`, and `TASKS.md` to reflect the actual repo state

---

## High Priority

- [ ] Add auth middleware and session protection for backend/frontend workflows
- [ ] Replace mock `fhir_service.py` behavior with real FHIR/EHR integration
- [ ] Rotate/remove sensitive local credentials from `backend/.env` if they have been exposed outside the machine

---

## Medium Priority

- [ ] Staff portal: add intake session review UI using `/intake/session/{session_id}`
- [ ] Staff portal: add follow-up response review UI using `/followups/{task_id}/responses`
- [ ] Staff portal: add report/clinical brief UI using existing report routes
- [ ] Persist AI engine parsed/prefilled/report caches into Postgres instead of process memory
- [ ] Add recency rules for historical prefill fields so older patient-confirmed values can be flagged for revalidation
- [ ] Show stronger freshness/warning states in the UI for stale reused values
- [ ] Staff portal: show clearer success/error states around assign/prefill/schedule actions
- [ ] Patient check-in: use `visit_id` hint on `/verify` to reduce re-entry friction
- [ ] Patient check-in: add true voice answer capture instead of read-aloud only
- [ ] Add automated smoke tests for critical backend routes
- [ ] Add frontend smoke or E2E coverage for the two main flows
- [ ] Improve build/runtime documentation in root `README.md` and frontend READMEs to match the current app state

---

## Low Priority

- [ ] Wire intake call scheduling to optionally trigger outbound dialing automatically
- [ ] Wire follow-up scheduling to optionally trigger outbound dialing automatically
- [ ] Improve DOB parsing and telephony normalization further
- [ ] Add structured JSON logging
- [ ] Add retry/error-budget handling around external AI calls

---

## Current Known Issues

- [ ] The staff portal is still missing transcript/review/report screens after setup actions are complete
- [ ] AI report caches still reset on backend restart even though workflow data and completed forms are in Postgres

---

## Current Local Run Sequence

```bash
# Terminal 1
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2
cd frontend/staff-portal
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# Terminal 3
cd frontend/patient-checkin
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```
