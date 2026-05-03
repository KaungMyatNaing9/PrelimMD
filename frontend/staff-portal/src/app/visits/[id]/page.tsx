"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  assignForm,
  getIntakeOverview,
  getPatient,
  getQuestionBank,
  getTemplates,
  getVisit,
  getVisitForms,
  scheduleFollowUp,
  scheduleIntakeCall,
  triggerPrefill,
  type AssignedForm,
  type FollowUpQuestion,
  type FormTemplate,
  type IntakeCallSchedule,
  type IntakeOverview,
  type Patient,
  type ScheduledVisit,
} from "@/lib/api";

function Badge({ status }: { status: string }) {
  const classes: Record<string, string> = {
    assigned: "badge badge-assigned",
    prefilled: "badge badge-prefilled",
    in_call: "badge badge-scheduled",
    completed: "badge badge-completed",
    scheduled: "badge badge-scheduled",
    checked_in: "badge badge-completed",
  };

  return <span className={classes[status] ?? "pill"}>{status.replace("_", " ")}</span>;
}

export default function VisitDetailPage() {
  const { id } = useParams<{ id: string }>();

  const [visit, setVisit] = useState<ScheduledVisit | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [forms, setForms] = useState<AssignedForm[]>([]);
  const [templates, setTemplates] = useState<FormTemplate[]>([]);
  const [questions, setQuestions] = useState<FollowUpQuestion[]>([]);
  const [overview, setOverview] = useState<IntakeOverview | null>(null);
  const [scheduledCall, setScheduledCall] = useState<IntakeCallSchedule | null>(null);

  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [selectedQuestions, setSelectedQuestions] = useState<Set<string>>(new Set());
  const [followUpDate, setFollowUpDate] = useState("");
  const [intakeCallDate, setIntakeCallDate] = useState("");

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [toast, setToast] = useState("");

  const showToast = useCallback((message: string) => {
    setToast(message);
    setTimeout(() => setToast(""), 3000);
  }, []);

  const loadVisit = useCallback(async () => {
    if (!id) return;

    const [visitData, formData, templateData, questionData, overviewData] = await Promise.all([
      getVisit(id),
      getVisitForms(id),
      getTemplates(),
      getQuestionBank(),
      getIntakeOverview(id),
    ]);

    setVisit(visitData);
    setForms(formData);
    setTemplates(templateData);
    setQuestions(questionData);
    setOverview(overviewData);

    const patientData = await getPatient(visitData.patient_id);
    setPatient(patientData);
  }, [id]);

  useEffect(() => {
    if (!id) return;

    loadVisit()
      .catch(() => showToast("We couldn't load the full visit workflow."))
      .finally(() => setLoading(false));
  }, [id, loadVisit, showToast]);

  const selectedTemplateMeta = useMemo(
    () => templates.find((template) => template.template_id === selectedTemplate),
    [selectedTemplate, templates]
  );

  const handleAssign = async () => {
    if (!selectedTemplate || !visit) return;

    setBusy("assign");
    try {
      await assignForm(visit.visit_id, selectedTemplate, "staff-002");
      setSelectedTemplate("");
      await loadVisit();
      showToast("Form assigned successfully.");
    } catch {
      showToast("Failed to assign form.");
    } finally {
      setBusy("");
    }
  };

  const handlePrefill = async () => {
    if (!visit) return;

    setBusy("prefill");
    try {
      await triggerPrefill(visit.visit_id);
      await loadVisit();
      showToast("EHR prefill complete.");
    } catch {
      showToast("Prefill failed.");
    } finally {
      setBusy("");
    }
  };

  const handleScheduleIntakeCall = async () => {
    if (!visit || !intakeCallDate) return;

    setBusy("intake-call");
    try {
      const scheduled = await scheduleIntakeCall(visit.visit_id, new Date(intakeCallDate).toISOString());
      setScheduledCall(scheduled);
      await loadVisit();
      showToast("Pre-visit intake call scheduled.");
    } catch {
      showToast("Failed to schedule intake call.");
    } finally {
      setBusy("");
    }
  };

  const handleScheduleFollowUp = async () => {
    if (!visit || selectedQuestions.size === 0 || !followUpDate) return;

    setBusy("followup");
    try {
      await scheduleFollowUp({
        patient_id: visit.patient_id,
        visit_id: visit.visit_id,
        created_by: "staff-001",
        scheduled_at: new Date(followUpDate).toISOString(),
        question_bank_ids: Array.from(selectedQuestions),
        custom_questions: [],
      });
      setSelectedQuestions(new Set());
      setFollowUpDate("");
      showToast("Follow-up call scheduled.");
    } catch {
      showToast("Failed to schedule follow-up.");
    } finally {
      setBusy("");
    }
  };

  const toggleQuestion = (questionId: string) => {
    setSelectedQuestions((current) => {
      const next = new Set(current);
      if (next.has(questionId)) {
        next.delete(questionId);
      } else {
        next.add(questionId);
      }
      return next;
    });
  };

  if (loading) {
    return (
      <div className="page">
        <div className="loading">Loading visit workflow...</div>
      </div>
    );
  }

  if (!visit) {
    return (
      <div className="page">
        <div className="empty">Visit not found.</div>
      </div>
    );
  }

  const checkinUrl = `http://localhost:3001/verify?visit_id=${visit.visit_id}`;
  const overallCompletion = overview?.completion_percent ?? 0;

  return (
    <div className="page">
      {toast ? <div className="toast">{toast}</div> : null}

      <Link href="/" className="back-link">
        Back to dashboard
      </Link>

      <section className="page-hero">
        <div>
          <div className="eyebrow">Visit Detail</div>
          <h2>{patient ? `${patient.first_name} ${patient.last_name}` : visit.patient_id}</h2>
          <p>
            Track intake completion, see exactly what still needs to be collected, and route the
            patient to kiosk or voice outreach without leaving this workflow.
          </p>
        </div>
        <div className="page-hero-actions">
          <Badge status={visit.status} />
          <a href={checkinUrl} target="_blank" rel="noreferrer" className="btn btn-primary">
            Open patient kiosk
          </a>
        </div>
      </section>

      <section className="metric-grid">
        <article className="metric-card soft-blue">
          <div className="metric-kicker">Intake Completion</div>
          <div className="metric-value" style={{ fontSize: "1.8rem" }}>
            {overallCompletion}%
          </div>
          <div className="metric-note">Across all assigned intake fields.</div>
        </article>
        <article className="metric-card soft-teal">
          <div className="metric-kicker">Fields Filled</div>
          <div className="metric-value" style={{ fontSize: "1.8rem" }}>
            {overview?.filled_fields ?? 0}
          </div>
          <div className="metric-note">Known from EHR, kiosk, or prior prefill.</div>
        </article>
        <article className="metric-card soft-amber">
          <div className="metric-kicker">Remaining For Call</div>
          <div className="metric-value" style={{ fontSize: "1.8rem" }}>
            {overview?.call_remaining_fields ?? 0}
          </div>
          <div className="metric-note">Call-safe prompts the nurse can schedule now.</div>
        </article>
        <article className="metric-card soft-green">
          <div className="metric-kicker">Provider</div>
          <div className="metric-value" style={{ fontSize: "1.35rem", lineHeight: 1.15 }}>
            {visit.provider_name}
          </div>
          <div className="metric-note">{visit.department}</div>
        </article>
      </section>

      <section className="split-grid">
        <div className="stack-list">
          <section className="panel">
            <div className="section-head">
              <div>
                <div className="eyebrow">Patient Snapshot</div>
                <h2>Clinical context</h2>
              </div>
            </div>

            <div className="detail-grid">
              <div className="detail-item">
                <div className="detail-label">Visit Date</div>
                <div className="detail-value">
                  {visit.visit_date} at {visit.visit_time}
                </div>
              </div>
              <div className="detail-item">
                <div className="detail-label">Reason</div>
                <div className="detail-value">{visit.reason}</div>
              </div>
              <div className="detail-item">
                <div className="detail-label">Department</div>
                <div className="detail-value">{visit.department}</div>
              </div>
              <div className="detail-item">
                <div className="detail-label">Provider</div>
                <div className="detail-value">{visit.provider_name}</div>
              </div>
              {patient ? (
                <>
                  <div className="detail-item">
                    <div className="detail-label">Date of Birth</div>
                    <div className="detail-value">{patient.date_of_birth}</div>
                  </div>
                  <div className="detail-item">
                    <div className="detail-label">Phone</div>
                    <div className="detail-value">{patient.phone}</div>
                  </div>
                  <div className="detail-item">
                    <div className="detail-label">Insurance</div>
                    <div className="detail-value">{patient.insurance_provider ?? "-"}</div>
                  </div>
                  <div className="detail-item">
                    <div className="detail-label">Address</div>
                    <div className="detail-value">{patient.address ?? "-"}</div>
                  </div>
                </>
              ) : null}
            </div>
          </section>

          <section className="panel">
            <div className="section-head">
              <div>
                <div className="eyebrow">Intake Forms</div>
                <h2>Assigned templates</h2>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={handlePrefill} disabled={busy === "prefill"}>
                {busy === "prefill" ? "Running..." : "Run EHR prefill"}
              </button>
            </div>

            {forms.length === 0 ? (
              <div className="empty">No forms assigned yet.</div>
            ) : (
              <div className="form-card-grid">
                {forms.map((form) => {
                  const template = templates.find((item) => item.template_id === form.template_id);
                  const summary = overview?.forms.find((item) => item.assignment_id === form.assignment_id);

                  return (
                    <div key={form.assignment_id} className="form-strip">
                      <div className="form-strip-copy">
                        <div className="form-strip-title">{template?.name ?? form.template_id}</div>
                        <div className="form-strip-meta">
                          Assigned {new Date(form.assigned_at).toLocaleDateString()} ·{" "}
                          {summary
                            ? `${summary.filled_fields}/${summary.total_fields} fields filled`
                            : template?.description ?? "No description"}
                        </div>
                        {summary ? (
                          <div className="mini-progress">
                            <div className="mini-progress-bar" style={{ width: `${summary.completion_percent}%` }} />
                          </div>
                        ) : null}
                      </div>
                      <Badge status={summary?.status ?? form.status} />
                    </div>
                  );
                })}
              </div>
            )}

            <div className="form-actions">
              <div className="field" style={{ flex: 1 }}>
                <label>Assign a form template</label>
                <select
                  className="select"
                  value={selectedTemplate}
                  onChange={(event) => setSelectedTemplate(event.target.value)}
                >
                  <option value="">Select template</option>
                  {templates.map((template) => (
                    <option key={template.template_id} value={template.template_id}>
                      {template.name}
                    </option>
                  ))}
                </select>
                {selectedTemplateMeta ? <div className="helper-text">{selectedTemplateMeta.description}</div> : null}
              </div>
              <button
                className="btn btn-primary"
                onClick={handleAssign}
                disabled={!selectedTemplate || busy === "assign"}
              >
                {busy === "assign" ? "Assigning..." : "Assign form"}
              </button>
            </div>
          </section>

          <section className="panel">
            <div className="section-head">
              <div>
                <div className="eyebrow">Intake Readiness</div>
                <h2>Filled vs remaining</h2>
              </div>
            </div>

            {overview?.forms.length ? (
              <div className="readiness-list">
                {overview.forms.map((form) => (
                  <div key={form.assignment_id} className="readiness-card">
                    <div className="readiness-top">
                      <div>
                        <div className="form-strip-title">{form.form_name}</div>
                        <div className="form-strip-meta">
                          {form.filled_fields} filled · {form.remaining_fields} remaining · {form.call_remaining_fields} by call
                        </div>
                      </div>
                      <div className="readiness-percent">{form.completion_percent}%</div>
                    </div>
                    <div className="mini-progress">
                      <div className="mini-progress-bar" style={{ width: `${form.completion_percent}%` }} />
                    </div>
                    <div className="chip-row">
                      {form.remaining_field_labels.length ? (
                        form.remaining_field_labels.map((label) => (
                          <span key={`${form.assignment_id}-${label}`} className="soft-chip">
                            {label}
                          </span>
                        ))
                      ) : (
                        <span className="soft-chip soft-chip-complete">All fields covered</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty">Assign a form to start intake tracking.</div>
            )}
          </section>
        </div>

        <div className="stack-list">
          <section className="action-card">
            <div className="eyebrow">Pre-Visit Voice Call</div>
            <h3>Schedule missing-field outreach</h3>
            <p className="helper-text" style={{ marginTop: "0.45rem" }}>
              The nurse can schedule a call that targets only the remaining call-safe fields.
            </p>
            <div className="helper-note" style={{ marginTop: "1rem" }}>
              {overview?.call_remaining_fields
                ? `${overview.call_remaining_fields} call-safe field(s) are still open across ${overview.total_forms} form(s).`
                : "No call-safe fields are currently left. The patient can continue on kiosk for review and signature."}
            </div>

            <div className="field" style={{ marginTop: "1rem" }}>
              <label>Call date and time</label>
              <input
                type="datetime-local"
                className="input"
                value={intakeCallDate}
                onChange={(event) => setIntakeCallDate(event.target.value)}
              />
            </div>

            <div className="question-list question-list-compact">
              {overview?.forms.flatMap((form) =>
                form.call_questions.map((question, index) => (
                  <div key={`${form.assignment_id}-${index}`} className="question-item selected">
                    <div>
                      <div className="question-text">{question}</div>
                      <div className="question-cat">{form.form_name}</div>
                    </div>
                  </div>
                ))
              )}
              {!overview?.forms.some((form) => form.call_questions.length) ? (
                <div className="empty-inline">No voice-call prompts are pending for this visit.</div>
              ) : null}
            </div>

            <div className="btn-row" style={{ marginTop: "1rem" }}>
              <button
                className="btn btn-primary"
                onClick={handleScheduleIntakeCall}
                disabled={!intakeCallDate || busy === "intake-call"}
              >
                {busy === "intake-call" ? "Scheduling..." : "Schedule intake call"}
              </button>
            </div>

            {scheduledCall ? (
              <div className="helper-note" style={{ marginTop: "1rem" }}>
                Session {scheduledCall.session_id} created. Voice start path: {scheduledCall.voice_start_path}
                {scheduledCall.patient_phone ? ` · Phone: ${scheduledCall.patient_phone}` : ""}
              </div>
            ) : null}
          </section>

          <section className="action-card">
            <div className="eyebrow">Kiosk Handoff</div>
            <h3>Patient-facing launch</h3>
            <p className="helper-text" style={{ marginTop: "0.45rem" }}>
              Use the kiosk link once the intake forms are assigned so the patient can review what
              is already filled and complete anything still missing.
            </p>
            <div className="helper-note" style={{ marginTop: "1rem" }}>
              Self check-in verifies identity, confirms prefilled fields, captures any missing
              details, and records consent in one guided flow.
            </div>
            <div className="btn-row" style={{ marginTop: "1rem" }}>
              <a href={checkinUrl} target="_blank" rel="noreferrer" className="btn btn-primary">
                Open kiosk experience
              </a>
            </div>
          </section>

          <section className="action-card">
            <div className="section-head">
              <div>
                <div className="eyebrow">Post-Discharge</div>
                <h3>Schedule follow-up call</h3>
              </div>
            </div>

            <div className="field" style={{ marginBottom: "1rem" }}>
              <label>Call date and time</label>
              <input
                type="datetime-local"
                className="input"
                value={followUpDate}
                onChange={(event) => setFollowUpDate(event.target.value)}
              />
            </div>

            <div className="eyebrow" style={{ marginBottom: "0.6rem" }}>
              Question set ({selectedQuestions.size} selected)
            </div>
            <div className="question-list">
              {questions.map((question) => (
                <div
                  key={question.question_id}
                  className={`question-item${selectedQuestions.has(question.question_id) ? " selected" : ""}`}
                  onClick={() => toggleQuestion(question.question_id)}
                >
                  <input type="checkbox" readOnly checked={selectedQuestions.has(question.question_id)} />
                  <div>
                    <div className="question-text">{question.text}</div>
                    <div className="question-cat">{question.category}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="btn-row" style={{ marginTop: "1rem" }}>
              <button
                className="btn btn-primary"
                onClick={handleScheduleFollowUp}
                disabled={selectedQuestions.size === 0 || !followUpDate || busy === "followup"}
              >
                {busy === "followup" ? "Scheduling..." : "Schedule follow-up call"}
              </button>
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}
