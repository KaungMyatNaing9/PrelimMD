# PrelimMD — System State

Last updated: 2026-05-04

---

## Current Status

PrelimMD currently consists of:

- A FastAPI backend in `backend/`
- A Next.js patient kiosk app in `frontend/patient-checkin/`
- A Next.js staff portal app in `frontend/staff-portal/`

This is no longer a backend-only repo. Both frontends exist and are wired to real backend routes, but there are still a few setup and product gaps before the full workflow feels complete.

As of the latest pass, the staff portal navigation/runtime has been rebuilt and now uses a single consistent route shell instead of the older mixed layout structure that caused hydration failures.

### Intended Workflow

1. Staff creates or selects a patient and schedules a visit.
2. Staff opens the visit workspace and either assigns an existing template or uploads/scans a new form to create one.
3. AI prefill runs immediately after assignment and generates:
   - prefilled known fields
   - remaining conversational follow-up prompts for kiosk or guided voice completion
4. Patient arrives and self check-in verifies identity, reviews stale/prefilled values, fills only the missing fields, and signs consent.
5. The visit status updates to `checked_in` in the staff portal.

---

## Local Run Commands

### 1. Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend docs:

- Swagger UI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

### 2. Patient Check-In

First install dependencies once:

```bash
cd frontend/patient-checkin
npm ci
```

Run it:

```bash
cd frontend/patient-checkin
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Local URL:

- `http://localhost:3001`

### 3. Staff Portal

First install dependencies once:

```bash
cd frontend/staff-portal
npm ci
```

Run it:

```bash
cd frontend/staff-portal
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Optional if you want the "Open patient kiosk" button to point somewhere other than local port `3001`:

```bash
NEXT_PUBLIC_PATIENT_CHECKIN_URL=http://localhost:3001
```

Local URL:

- `http://localhost:3000`

### Recommended terminal layout

Use three terminals:

1. backend on `:8000`
2. staff portal on `:3000`
3. patient check-in on `:3001`

---

## How The Pieces Connect

```text
Staff Portal (Next.js :3000)
  ├─ POST /patients
  ├─ POST /visits
  ├─ GET /patients
  ├─ GET /visits
  ├─ GET /visits/{id}/forms
  ├─ GET /intake/templates
  ├─ POST /intake/templates/upload
  ├─ GET /intake/overview/{visit_id}
  ├─ POST /intake/assign
  ├─ POST /intake/prefill/{visit_id}
  ├─ GET /followups/question-bank
  ├─ GET /followups
  └─ POST /followups/schedule

Patient Check-In (Next.js :3001)
  ├─ POST /patient/validate
  ├─ POST /patient/new-checkin
  ├─ GET /patient/checkin/{visit_id}/forms
  ├─ POST /patient/checkin/{visit_id}/submit
  └─ POST /patient/checkin/{visit_id}/sign

FastAPI Backend (:8000)
  ├─ Postgres-backed store
  ├─ completed-form history persisted in Postgres
  ├─ normalized reusable patient history tables for meds/allergies/conditions
  ├─ intake / follow-up orchestration
  ├─ OCR + template parsing + prefill logic
  ├─ voice/Twilio routes
  └─ legacy forms/report routes
```

Both frontends use `NEXT_PUBLIC_API_URL` and otherwise fall back to `http://localhost:8000`.

---

## What Is Implemented Now

### Backend

Implemented and verified from code:

- Patients API
- Visits API
- Intake templates, upload, assignment, prefill, readiness overview
- DB-first prefill using patient record, visit record, prior intake sessions, and prior completed forms
- Freshness/staleness classification for reused patient-confirmed values
- Patient identity validation
- Returning-patient kiosk form review and submission
- New-patient kiosk profile creation
- Staff-side template upload/scan route
- Follow-up question bank and task scheduling
- Interview/session orchestration
- Voice/Twilio endpoints
- Legacy forms/report routes kept in place

Validation completed:

- `venv/bin/python -c "from app.main import app; print(app.version)"` passed
- `venv/bin/python -m compileall app` passed

### Patient Check-In Frontend

Implemented pages:

- `/`
- `/verify`
- `/new-patient`
- `/checkin/[visit_id]`
- `/complete`

Implemented behavior:

- returning-patient identity verification
- first-time patient profile creation
- merged prefilled field review/edit across duplicated form fields
- stale-value revalidation before continuation
- complete missing-field completion across all remaining questions
- typed-signature consent submit
- per-question speaker playback
- per-question microphone dictation
- guided voice assistant mode with conversational prompts and explanation help
- final merged review before signature

Validation completed:

- `npx tsc --noEmit` passed

### Staff Portal Frontend

Implemented pages:

- `/`
- `/calls`
- `/forms-library`
- `/visits`
- `/patients`
- `/risk-alerts`
- `/visits/[id]`
- `/followups`
- `/followups/[id]`

Implemented behavior:

- dashboard with schedule, call, completion, and risk summaries
- patient creation and visit scheduling
- patient roster search
- scheduled visit queue
- visit detail workflow
- assign saved form templates
- assign any library template regardless of department, with department suggestions highlighted
- upload/scan new forms from staff side
- auto-trigger prefill after assignment/upload
- intake overview display
- intake progress view backed by stored intake sessions
- forms library view backed by stored templates
- risk alerts view backed by follow-up flags
- open patient kiosk link
- auto-refresh on focus/interval for staff-visible visit status updates

Validation completed:

- `npx tsc --noEmit` passed
- `npm run lint` passed
- `npm run build` passed

---

## What Is Still Missing Or Weak

### Frontend/runtime blockers

1. The staff portal now supports setup workflows and core navigation, but review workflows are still thin.

2. The patient verify page accepts a `visit_id` hint but does not currently use it to streamline lookup.

### Product/UI gaps

1. The staff portal does not yet expose:
   - intake session transcript/review
   - follow-up responses review
   - report/clinical brief review

2. There is no auth on either frontend or backend.

3. Patient-side voice assistance is browser-based and conversational, but not yet a full realtime backend agent/avatar stack.

### Platform gaps

1. Core workflow data is now stored in Postgres, and completed intake forms are now persisted too, but AI report caches are still process-memory only.
2. `fhir_service.py` is still mock-only.
3. Voice scheduling still exists in backend routes, but the staff portal MVP now treats voice help as optional guided intake rather than a promised outbound-call workflow.
4. Build/test automation is minimal.

### Security gap

`backend/.env` currently contains real-looking service credentials. That file should remain local-only, be excluded from sharing, and the current keys should be rotated if they were ever exposed outside the developer machine.

---

## Verified Build/Check Notes

### Backend

- Import: passed
- Python compile: passed

### Patient Check-In

- `npm ci`: completed
- `npx tsc --noEmit`: passed
- `npm run lint`: passed
- `npm run build`: passed

### Staff Portal

- `npm ci`: completed
- `npx tsc --noEmit`: passed
- `npm run lint`: passed
- `npm run build`: passed
- `npm run build`: passed

### Staff Portal

- `npm ci`: completed
- `npx tsc --noEmit`: passed
- `npm run lint`: passed
- `npm run build`: passed

---

## Seeded Data Notes

The backend still uses seeded/mock data from `app/services/store.py`, including:

- patients
- visits
- templates
- assignments
- follow-up question bank
- at least one seeded follow-up task

This is enough to exercise the current frontends locally. The seeded dataset is written into Postgres on first initialization and then persists across restarts unless the database volume is reset.
