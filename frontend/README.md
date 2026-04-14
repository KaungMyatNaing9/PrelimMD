# PrelimMD — Frontend

Next.js 14 + TypeScript application.

## Getting Started

```bash
npm install
cp .env.example .env.local   # fill in values
npm run dev                   # http://localhost:3000
```

## Key Directories

| Path | Purpose |
|---|---|
| `src/app/` | Next.js App Router pages |
| `src/components/` | Reusable UI components |
| `src/lib/api.ts` | Typed fetch helpers to call the backend |
| `src/styles/` | Global CSS / Tailwind base |

## Owner

Frontend teammate — coordinate with Backend on API contract in `shared/types/`.
