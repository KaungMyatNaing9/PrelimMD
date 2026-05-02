# Patient Self Check-In / Kiosk Portal — Placeholder

> **Not implemented yet.** This folder is reserved for the Patient Check-In frontend.

## What goes here

A React/Next.js application displayed on a self-service kiosk (or patient's device) used during the check-in process:

- Patient validates identity by entering name, date of birth, and visit date
- Patient reviews prefilled intake forms (auto-filled from EHR and pre-visit call)
- Patient completes any fields still marked as missing
- Patient reviews and corrects any incorrectly prefilled fields
- Patient provides electronic consent signature
- Patient finalizes and submits the check-in

## Backend APIs it will consume

All endpoints are implemented and available at `http://localhost:8000`. See `SYSTEM_STATE.md` in the repo root for the full API reference.

Key routes for this portal:
- `POST /patient/validate` — verify identity (name + DOB + visit date)
- `GET /patient/checkin/{visit_id}/forms` — get prefilled forms with missing/confirm fields highlighted
- `POST /patient/checkin/{visit_id}/submit` — save patient's answers and corrections
- `POST /patient/checkin/{visit_id}/sign` — record consent signature

## Setup (when ready to build)

```bash
cd frontend/patient-checkin
npm install
npm run dev
# Runs on http://localhost:5173 by default (Vite) or 3001 (Next.js)
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in a `.env.local` file.

## Design notes

- Should be optimized for touch screen / kiosk use
- Large font sizes, minimal typing, confirm/edit flow
- Show progress bar (Step 1 of 4, etc.)
- Should not require login — identity is verified via name + DOB + visit date
