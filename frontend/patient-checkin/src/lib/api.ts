const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `POST ${path} → ${res.status}`);
  }
  return res.json();
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function postForm<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `POST ${path} → ${res.status}`);
  }
  return res.json();
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ValidateResponse {
  valid: boolean;
  message: string;
  patient?: { patient_id: string; first_name: string; last_name: string };
  visit?: { visit_id: string; visit_date: string; department: string };
}

export interface CheckInField {
  field_id: string;
  label: string;
  type: string;
  required: boolean;
  section: string;
  prefilled_value?: string | boolean | null;
  source?: string | null;
  last_confirmed_at?: string | null;
  needs_confirmation: boolean;
  is_missing: boolean;
}

export interface CheckInFormGroup {
  assignment_id: string;
  form_name: string;
  fields: CheckInField[];
}

export interface CheckInFormsResponse {
  visit_id: string;
  patient_id: string;
  forms: CheckInFormGroup[];
  total_missing: number;
  total_needs_confirmation: number;
}

export interface CheckInScannedField {
  field_id: string;
  label: string;
  value: string | boolean | number;
  confidence: number;
  field_type: string;
  section: string;
  source: string;
}

export interface CheckInScanResponse {
  visit_id: string;
  scanned_fields: CheckInScannedField[];
  applied_count: number;
  ocr_preview?: string | null;
  message: string;
}

export interface NewPatientCheckInPayload {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  phone: string;
  appointment_date: string;
  appointment_time: string;
  reason_for_visit: string;
  email?: string;
  address?: string;
  insurance_provider?: string;
  insurance_id?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  emergency_contact_relation?: string;
  department?: string;
  provider_name?: string;
}

export interface NewPatientCheckInResponse {
  assignment_id: string;
  message: string;
  patient: {
    patient_id: string;
    first_name: string;
    last_name: string;
    date_of_birth: string;
  };
  visit: {
    visit_id: string;
    visit_date: string;
    visit_time: string;
    department: string;
  };
}

// ─── API calls ────────────────────────────────────────────────────────────────

export const validateIdentity = (
  first_name: string,
  last_name: string,
  date_of_birth: string,
  appointment_date: string
) => post<ValidateResponse>("/patient/validate", { first_name, last_name, date_of_birth, appointment_date });

export const createNewPatientCheckin = (payload: NewPatientCheckInPayload) =>
  post<NewPatientCheckInResponse>("/patient/new-checkin", payload);

export const getCheckinForms = (visitId: string) =>
  get<CheckInFormsResponse>(`/patient/checkin/${visitId}/forms`);

export const scanCheckinForm = (visitId: string, file: Blob, filename = "camera-scan.jpg") => {
  const formData = new FormData();
  formData.append("file", file, filename);
  return postForm<CheckInScanResponse>(`/patient/checkin/${visitId}/scan`, formData);
};

export const submitCheckin = (visitId: string, answers: Record<string, unknown>) =>
  post(`/patient/checkin/${visitId}/submit`, { answers });

export const signConsent = (visitId: string, signature: string) =>
  post(`/patient/checkin/${visitId}/sign`, { signature, signed_at: new Date().toISOString() });
