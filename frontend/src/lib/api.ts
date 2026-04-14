// src/lib/api.ts
// Centralised fetch helpers for calling the FastAPI backend.
// All components should import from here — never call fetch() directly in a component.
//
// TODO: Frontend - add typed request/response wrappers for each route:
//   - POST /interview/start
//   - POST /interview/respond
//   - GET  /report/:sessionId
//   - POST /scheduling/book
// TODO: Frontend - add auth header injection once auth is wired up

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// TODO: Frontend - replace with real typed API client
export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }

  return res.json() as Promise<T>;
}
