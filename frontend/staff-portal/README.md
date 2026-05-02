# Staff Portal — Placeholder

> **Not implemented yet.** This folder is reserved for the Staff Portal frontend.

## What goes here

A React/Next.js application used by nurses and doctors to:

- View the day's scheduled patients and their visit details
- Assign intake forms to a patient visit (selecting from uploaded templates)
- Trigger EHR prefill for an assigned form
- Schedule pre-visit intake calls for patients
- Schedule post-discharge follow-up calls with a custom question set
- Browse the follow-up question bank and add custom doctor questions
- Review collected intake answers, flagged fields, and follow-up responses
- Download or print the clinical brief for a patient

## Backend APIs it will consume

All endpoints are implemented and available at `http://localhost:8000`. See `SYSTEM_STATE.md` in the repo root for the full API reference.

Key routes for this portal:
- `GET /patients` — list all patients
- `GET /visits` — list scheduled visits
- `GET /forms/templates` — list available form templates
- `POST /forms/assign` — assign a form to a visit
- `POST /intake/prefill/{visit_id}` — trigger EHR prefill
- `POST /intake/schedule-call` — schedule a pre-visit intake call
- `GET /followups/question-bank` — browse question bank
- `POST /followups/schedule` — schedule a post-discharge follow-up
- `GET /followups` — list all follow-up tasks

## Setup (when ready to build)

```bash
cd frontend/staff-portal
npm install
npm run dev
# Runs on http://localhost:3000 by default
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in a `.env.local` file.
