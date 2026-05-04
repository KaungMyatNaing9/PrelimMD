"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  assignForm,
  getIntakeOverview,
  getPatient,
  getTemplates,
  getVisit,
  getVisitForms,
  triggerPrefill,
  uploadTemplate,
  type AssignedForm,
  type FormTemplate,
  type IntakeOverview,
  type Patient,
  type ScheduledVisit,
} from "@/lib/api";

const DEFAULT_STAFF_ID = process.env.NEXT_PUBLIC_DEFAULT_STAFF_ID || "staff-001";

function matchesDepartment(template: FormTemplate, department: string) {
  const category = template.category.toLowerCase();
  const lowerDepartment = department.toLowerCase();
  const rootDepartment = lowerDepartment.split(" ")[0] || lowerDepartment;
  return (
    category.includes("general") ||
    category.includes("intake") ||
    lowerDepartment.includes(category) ||
    category.includes(rootDepartment)
  );
}

export default function VisitDetailPage() {
  const params = useParams<{ id: string }>();
  const visitId = params.id;
  const patientCheckinBaseUrl = process.env.NEXT_PUBLIC_PATIENT_CHECKIN_URL || "http://localhost:3001";
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const cameraInputRef = useRef<HTMLInputElement | null>(null);

  const [visit, setVisit] = useState<ScheduledVisit | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [templates, setTemplates] = useState<FormTemplate[]>([]);
  const [assignedForms, setAssignedForms] = useState<AssignedForm[]>([]);
  const [overview, setOverview] = useState<IntakeOverview | null>(null);
  const [selectedTemplateIds, setSelectedTemplateIds] = useState<string[]>([]);
  const [uploadMeta, setUploadMeta] = useState({
    name: "",
    description: "",
    category: "custom_intake",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    if (!visitId) return;
    const visitData = await getVisit(visitId);
    const [patientData, templateData, formData] = await Promise.all([
      getPatient(visitData.patient_id),
      getTemplates(),
      getVisitForms(visitId),
    ]);

    setVisit(visitData);
    setPatient(patientData);
    setTemplates(templateData);
    setAssignedForms(formData);

    try {
      setOverview(await getIntakeOverview(visitId));
    } catch {
      setOverview(null);
    }
  }, [visitId]);

  useEffect(() => {
    load()
      .catch(() => setMessage("Could not load visit workspace."))
      .finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void load();
    }, 15000);
    const onFocus = () => void load();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [load]);

  const checkinUrl = useMemo(() => {
    if (!visit) return "#";
    return `${patientCheckinBaseUrl.replace(/\/$/, "")}/verify?visit_id=${visit.visit_id}`;
  }, [patientCheckinBaseUrl, visit]);

  const assignedTemplateIds = useMemo(
    () => new Set(assignedForms.map((form) => form.template_id)),
    [assignedForms]
  );

  const suggestedTemplates = useMemo(() => {
    if (!visit) return [];
    return templates.filter((template) => matchesDepartment(template, visit.department));
  }, [templates, visit]);

  async function handleAssignSelected() {
    if (!visit || selectedTemplateIds.length === 0) return;
    setSaving("assign");
    setMessage("");
    try {
      for (const templateId of selectedTemplateIds) {
        if (!assignedTemplateIds.has(templateId)) {
          await assignForm(visit.visit_id, templateId, DEFAULT_STAFF_ID);
        }
      }
      await triggerPrefill(visit.visit_id);
      await load();
      setSelectedTemplateIds([]);
      setMessage("Forms assigned and AI prefill completed.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to assign forms.");
    } finally {
      setSaving("");
    }
  }

  async function handleUpload(file: File) {
    if (!visit) return;
    setSaving("upload");
    setMessage("");
    try {
      const uploaded = await uploadTemplate(file, uploadMeta, file.name);
      await assignForm(visit.visit_id, uploaded.template.template_id, DEFAULT_STAFF_ID);
      await triggerPrefill(visit.visit_id);
      await load();
      setUploadMeta({ name: "", description: "", category: "custom_intake" });
      setMessage("Custom form uploaded, stored in the library, assigned, and prefilled.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to upload custom form.");
    } finally {
      setSaving("");
    }
  }

  if (loading) {
    return <div className="card p-5 text-sm text-slate">Loading visit workspace...</div>;
  }

  if (!visit || !patient) {
    return <div className="card p-5 text-sm text-coral">Visit not found.</div>;
  }

  return (
    <div className="space-y-6">
      {message ? <section className="card p-4 text-sm text-slate">{message}</section> : null}

      <section className="card p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <Link href="/patients" className="text-sm font-semibold text-teal hover:text-navy">
              ← Back to patients
            </Link>
            <div className="mt-3 text-xs font-semibold uppercase tracking-[0.18em] text-teal">Patient Intake Workspace</div>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-navy">
              {patient.first_name} {patient.last_name}
            </h2>
            <p className="mt-2 max-w-3xl text-sm text-slate">
              Use this screen to assign existing intake templates, upload a paper form or photo,
              run AI prefill, and then send the patient into self check-in.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <a href={checkinUrl} target="_blank" rel="noreferrer" className="btn-secondary">
              Open Patient Check-in
            </a>
            <Link href="/calls" className="btn-primary">
              View Intake Progress
            </Link>
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-3xl bg-slate-50 p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate">Patient</div>
            <div className="mt-2 font-semibold text-navy">{patient.date_of_birth}</div>
            <div className="mt-1 text-sm text-slate">{patient.phone || "No phone on file"}</div>
          </div>
          <div className="rounded-3xl bg-slate-50 p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate">Visit</div>
            <div className="mt-2 font-semibold text-navy">{visit.visit_date} at {visit.visit_time}</div>
            <div className="mt-1 text-sm text-slate">{visit.department} · {visit.provider_name}</div>
          </div>
          <div className="rounded-3xl bg-slate-50 p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate">EHR Status</div>
            <div className="mt-2 font-semibold text-navy">
              {overview ? `${overview.filled_fields} of ${overview.total_fields} fields known` : "No forms assigned yet"}
            </div>
            <div className="mt-3 h-2 rounded-full bg-slate-200">
              <div
                className="h-2 rounded-full bg-teal transition-all"
                style={{ width: `${overview?.completion_percent ?? 0}%` }}
              />
            </div>
          </div>
          <div className="rounded-3xl bg-slate-50 p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate">Visit Status</div>
            <div className="mt-2 font-semibold text-navy">{visit.status.replace("_", " ")}</div>
            <div className="mt-1 text-sm text-slate">
              {visit.status === "checked_in" ? "Patient has finished kiosk review and signature." : `${overview?.remaining_fields ?? 0} kiosk fields still need review`}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,1fr)]">
        <div className="space-y-6">
          <section className="card p-5">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Select Forms</div>
              <h3 className="mt-2 text-xl font-semibold text-navy">Assign existing templates</h3>
              <p className="mt-2 text-sm text-slate">
                All templates in the library are available here. Suggested options are highlighted based on the visit department, but you can assign any category.
              </p>
            </div>

            <div className="mt-5 grid gap-3">
              {templates.map((template) => {
                const checked = selectedTemplateIds.includes(template.template_id) || assignedTemplateIds.has(template.template_id);
                const suggested = suggestedTemplates.some((item) => item.template_id === template.template_id);
                return (
                  <label key={template.template_id} className="flex items-start gap-3 rounded-3xl border border-slate-200 p-4">
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 rounded border-slate-300 text-teal focus:ring-teal"
                      checked={checked}
                      disabled={assignedTemplateIds.has(template.template_id)}
                      onChange={(event) => {
                        setSelectedTemplateIds((current) => {
                          const next = new Set(current);
                          if (event.target.checked) next.add(template.template_id);
                          else next.delete(template.template_id);
                          return Array.from(next);
                        });
                      }}
                    />
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="font-semibold text-navy">{template.name}</div>
                        {suggested ? <span className="badge bg-teal-soft text-navy">Suggested for {visit.department}</span> : null}
                      </div>
                      <div className="mt-1 text-sm text-slate">{template.description}</div>
                      <div className="mt-2 text-xs uppercase tracking-[0.16em] text-slate">{template.category}</div>
                    </div>
                  </label>
                );
              })}
            </div>

            <div className="mt-5">
              <button className="btn-primary" onClick={handleAssignSelected} disabled={saving === "assign" || selectedTemplateIds.length === 0}>
                {saving === "assign" ? "Assigning..." : "Submit & Prefill"}
              </button>
            </div>
          </section>

          <section className="card p-5">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Upload Custom Form</div>
              <h3 className="mt-2 text-xl font-semibold text-navy">Scan PDF or camera image</h3>
              <p className="mt-2 text-sm text-slate">
                This is the staff-side camera flow. Uploaded forms are parsed, added to the forms library, assigned to the visit, and prefilled automatically.
              </p>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div>
                <label className="field-label">Template Name</label>
                <input className="field-input" value={uploadMeta.name} onChange={(event) => setUploadMeta((current) => ({ ...current, name: event.target.value }))} placeholder="Cardiology packet" />
              </div>
              <div>
                <label className="field-label">Category</label>
                <input className="field-input" value={uploadMeta.category} onChange={(event) => setUploadMeta((current) => ({ ...current, category: event.target.value }))} />
              </div>
              <div className="md:col-span-2">
                <label className="field-label">Description</label>
                <textarea className="field-input min-h-28" value={uploadMeta.description} onChange={(event) => setUploadMeta((current) => ({ ...current, description: event.target.value }))} placeholder="Scanned at front desk from clinic paper packet" />
              </div>
            </div>

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="mt-5 flex w-full flex-col items-center justify-center rounded-3xl border border-dashed border-teal/40 bg-teal-soft px-6 py-10 text-center transition hover:border-teal hover:bg-white"
            >
              <span className="text-sm font-semibold text-navy">Drop zone shortcut</span>
              <span className="mt-2 text-sm text-slate">Choose a PDF or image from this device.</span>
            </button>

            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" className="btn-secondary" onClick={() => fileInputRef.current?.click()} disabled={saving === "upload"}>
                {saving === "upload" ? "Uploading..." : "Upload PDF"}
              </button>
              <button type="button" className="btn-primary" onClick={() => cameraInputRef.current?.click()} disabled={saving === "upload"}>
                Use Camera
              </button>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,image/*"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void handleUpload(file);
                event.target.value = "";
              }}
            />
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void handleUpload(file);
                event.target.value = "";
              }}
            />
          </section>

          <section className="card p-5">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Assigned Forms</div>
              <h3 className="mt-2 text-xl font-semibold text-navy">Prefill and missing fields</h3>
            </div>

            <div className="mt-5 space-y-4">
              {overview?.forms.length ? (
                overview.forms.map((form) => (
                  <div key={form.assignment_id} className="rounded-3xl border border-slate-200 p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="font-semibold text-navy">{form.form_name}</div>
                        <div className="mt-1 text-sm text-slate">
                          {form.filled_fields}/{form.total_fields} fields known
                        </div>
                      </div>
                      <span className="badge bg-slate-100 text-slate-700">{form.status.replace("_", " ")}</span>
                    </div>
                    <div className="mt-3 h-2 rounded-full bg-slate-200">
                      <div className="h-2 rounded-full bg-teal" style={{ width: `${form.completion_percent}%` }} />
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {form.call_questions.length ? (
                        form.call_questions.map((question) => (
                          <span key={`${form.assignment_id}-${question}`} className="badge bg-teal-soft text-navy">
                            {question}
                          </span>
                        ))
                      ) : (
                        <span className="badge bg-emerald-100 text-emerald-700">No intake follow-up questions remain</span>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-3xl bg-slate-50 p-4 text-sm text-slate">No forms assigned yet.</div>
              )}
            </div>
          </section>
        </div>

        <div className="space-y-6">
          <section className="card p-5">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Intake Progress</div>
              <h3 className="mt-2 text-xl font-semibold text-navy">What still needs patient review</h3>
              <p className="mt-2 text-sm text-slate">
                This MVP keeps the handoff simple: assign forms, let AI prefill what it can, and use the kiosk or voice-guided patient flow for anything still missing.
              </p>
            </div>

            <div className="mt-5 rounded-3xl bg-slate-50 p-4 text-sm text-slate">
              <div className="font-semibold text-navy">{overview?.remaining_fields ?? 0} fields still need patient confirmation or completion</div>
              <div className="mt-2">
                {overview?.call_remaining_fields ?? 0} conversational follow-up prompts are available if the patient uses the guided voice assistant.
              </div>
              <div className="mt-4">
                <Link href={`/calls?visit_id=${visit.visit_id}`} className="btn-secondary">
                  Open Intake Progress
                </Link>
              </div>
            </div>
          </section>

          <section className="card p-5">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Visit Info</div>
              <h3 className="mt-2 text-xl font-semibold text-navy">Clinical context</h3>
            </div>
            <dl className="mt-5 space-y-4 text-sm">
              <div>
                <dt className="font-semibold text-slate">Reason for visit</dt>
                <dd className="mt-1 text-navy">{visit.reason || "Not entered"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate">Insurance ID</dt>
                <dd className="mt-1 text-navy">{patient.insurance_id || "Not on file"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate">Assigned templates</dt>
                <dd className="mt-1 text-navy">{assignedForms.length}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate">Remaining kiosk fields</dt>
                <dd className="mt-1 text-navy">{overview?.remaining_fields ?? 0}</dd>
              </div>
            </dl>
          </section>
        </div>
      </section>
    </div>
  );
}
