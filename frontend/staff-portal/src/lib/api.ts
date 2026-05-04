const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
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

export interface Patient {
  patient_id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  phone: string;
  email?: string;
  address?: string;
  insurance_provider?: string;
  insurance_id?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  emergency_contact_relation?: string;
}

export interface CreatePatientPayload {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  phone?: string;
  email?: string;
  address?: string;
  insurance_provider?: string;
  insurance_id?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  emergency_contact_relation?: string;
}

export interface ScheduledVisit {
  visit_id: string;
  patient_id: string;
  visit_date: string;
  visit_time: string;
  provider_name: string;
  department: string;
  reason: string;
  status: string;
}

export interface CreateVisitPayload {
  patient_id: string;
  visit_date: string;
  visit_time: string;
  provider_name: string;
  department: string;
  reason?: string;
  notes?: string;
}

export interface FormTemplate {
  template_id: string;
  name: string;
  description: string;
  category: string;
  fields?: Array<{ field_id: string; label: string; type: string; required: boolean; section: string }>;
}

export interface AssignedForm {
  assignment_id: string;
  visit_id: string;
  template_id: string;
  form_id?: string;
  assigned_by: string;
  assigned_at: string;
  status: string;
}

export interface IntakeFormOverview {
  assignment_id: string;
  template_id: string;
  form_name: string;
  status: string;
  total_fields: number;
  filled_fields: number;
  remaining_fields: number;
  call_remaining_fields: number;
  completion_percent: number;
  remaining_field_labels: string[];
  call_questions: string[];
}

export interface IntakeOverview {
  visit_id: string;
  patient_id: string;
  total_forms: number;
  total_fields: number;
  filled_fields: number;
  remaining_fields: number;
  call_remaining_fields: number;
  completion_percent: number;
  forms: IntakeFormOverview[];
}

export interface IntakeCallSchedule {
  visit_id: string;
  session_id: string;
  scheduled_at: string;
  status: string;
  remaining_fields: number;
  call_remaining_fields: number;
  patient_phone?: string;
  voice_start_path: string;
  note: string;
}

export interface IntakeSession {
  session_id: string;
  session_type: "intake" | "followup";
  visit_id?: string;
  task_id?: string;
  patient_id: string;
  status: "in_progress" | "completed" | "abandoned";
  conversation: Array<{
    turn_id: string;
    role: "ai" | "patient";
    content: string;
    timestamp: string;
    field_ids_targeted: string[];
  }>;
  collected_answers: Record<string, unknown>;
  flags: string[];
  created_at: string;
  completed_at?: string;
  current_question_index: number;
}

export interface FollowUpTask {
  task_id: string;
  patient_id: string;
  visit_id: string;
  created_by: string;
  scheduled_at: string;
  status: string;
  created_at: string;
  session_id?: string;
  results_summary?: string;
  flags: string[];
  questions: Array<{ question_id: string; text: string; category: string }>;
}

export interface FollowUpQuestion {
  question_id: string;
  text: string;
  category: string;
  concerning_keywords?: string[];
}

export interface UploadedTemplateResponse {
  template: FormTemplate;
  parsed_schema: {
    form_id: string;
    form_name: string;
    fields: Array<{ field_id: string; label: string; type: string; required: boolean; section: string }>;
  };
  message: string;
}

// ─── API calls ────────────────────────────────────────────────────────────────

export const getPatients = () => get<Patient[]>("/patients");
export const getPatient = (id: string) => get<Patient>(`/patients/${id}`);
export const createPatient = (payload: CreatePatientPayload) => post<Patient>("/patients", payload);

export const getVisits = (patientId?: string) =>
  get<ScheduledVisit[]>(patientId ? `/visits?patient_id=${patientId}` : "/visits");
export const getVisit = (id: string) => get<ScheduledVisit>(`/visits/${id}`);
export const getVisitForms = (id: string) => get<AssignedForm[]>(`/visits/${id}/forms`);
export const createVisit = (payload: CreateVisitPayload) => post<ScheduledVisit>("/visits", payload);

export const getTemplates = () => get<FormTemplate[]>("/intake/templates");
export const getIntakeOverview = (visitId: string) => get<IntakeOverview>(`/intake/overview/${visitId}`);
export const getIntakeSessions = () => get<IntakeSession[]>("/intake/sessions");
export const uploadTemplate = (
  file: Blob,
  payload: { name?: string; description?: string; category?: string },
  filename = "uploaded-form.pdf"
) => {
  const formData = new FormData();
  formData.append("file", file, filename);
  if (payload.name) formData.append("name", payload.name);
  if (payload.description) formData.append("description", payload.description);
  if (payload.category) formData.append("category", payload.category);
  return postForm<UploadedTemplateResponse>("/intake/templates/upload", formData);
};

export const assignForm = (visitId: string, templateId: string, assignedBy: string) =>
  post("/intake/assign", { visit_id: visitId, template_id: templateId, assigned_by: assignedBy });

export const triggerPrefill = (visitId: string) =>
  post(`/intake/prefill/${visitId}`, {});

export const scheduleIntakeCall = (visitId: string, scheduledAt: string) =>
  post<IntakeCallSchedule>("/intake/schedule-call", { visit_id: visitId, scheduled_at: scheduledAt });

export const getQuestionBank = () => get<FollowUpQuestion[]>("/followups/question-bank");

export const scheduleFollowUp = (payload: {
  patient_id: string;
  visit_id: string;
  created_by: string;
  scheduled_at: string;
  question_bank_ids: string[];
  custom_questions?: string[];
}) => post("/followups/schedule", payload);

export const getFollowUpTasks = (patientId?: string) =>
  get<FollowUpTask[]>(patientId ? `/followups?patient_id=${patientId}` : "/followups");
export const getFollowUpTask = (id: string) => get<FollowUpTask>(`/followups/${id}`);
