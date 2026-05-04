"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getFollowUpTask, getPatient, getVisit, type FollowUpTask, type Patient, type ScheduledVisit } from "@/lib/api";

export default function FollowUpDetailPage() {
  const params = useParams<{ id: string }>();
  const taskId = params.id;
  const [task, setTask] = useState<FollowUpTask | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [visit, setVisit] = useState<ScheduledVisit | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!taskId) return;
    getFollowUpTask(taskId)
      .then(async (taskData) => {
        setTask(taskData);
        const [patientData, visitData] = await Promise.all([
          getPatient(taskData.patient_id),
          getVisit(taskData.visit_id),
        ]);
        setPatient(patientData);
        setVisit(visitData);
      })
      .finally(() => setLoading(false));
  }, [taskId]);

  if (loading) {
    return <div className="card p-5 text-sm text-slate">Loading follow-up detail...</div>;
  }

  if (!task) {
    return <div className="card p-5 text-sm text-coral">Follow-up task not found.</div>;
  }

  return (
    <div className="space-y-6">
      <section className="card p-5">
        <Link href="/risk-alerts" className="text-sm font-semibold text-teal hover:text-navy">
          ← Back to alerts
        </Link>
        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-coral">Follow-up Task</div>
            <h2 className="mt-2 text-3xl font-semibold text-navy">
              {patient ? `${patient.first_name} ${patient.last_name}` : task.patient_id}
            </h2>
            <p className="mt-2 text-sm text-slate">
              Task {task.task_id} · scheduled {task.scheduled_at.slice(0, 16).replace("T", " ")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className={`badge ${task.flags.length ? "bg-rose-100 text-rose-700" : "bg-slate-100 text-slate-700"}`}>
              {task.status}
            </span>
            {visit ? (
              <Link href={`/visits/${visit.visit_id}`} className="btn-primary">
                Open Patient Workspace
              </Link>
            ) : null}
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(300px,0.9fr)]">
        <div className="card p-5">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Question Builder Output</div>
          <h3 className="mt-2 text-xl font-semibold text-navy">Configured follow-up questions</h3>
          <div className="mt-5 space-y-3">
            {task.questions.map((question, index) => (
              <div key={question.question_id} className="rounded-3xl border border-slate-200 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate">Question {index + 1}</div>
                <div className="mt-2 font-semibold text-navy">{question.text}</div>
                <div className="mt-2 text-sm text-slate">{question.category}</div>
              </div>
            ))}
          </div>
        </div>

        <aside className="space-y-6">
          <section className="card p-5">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Patient Detail</div>
            <h3 className="mt-2 text-xl font-semibold text-navy">Context</h3>
            <dl className="mt-5 space-y-4 text-sm">
              <div>
                <dt className="font-semibold text-slate">Phone</dt>
                <dd className="mt-1 text-navy">{patient?.phone || "Not on file"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate">Insurance</dt>
                <dd className="mt-1 text-navy">{patient?.insurance_provider || "Not on file"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-slate">Visit</dt>
                <dd className="mt-1 text-navy">{visit ? `${visit.visit_date} · ${visit.department}` : "Visit unavailable"}</dd>
              </div>
            </dl>
          </section>

          <section className="card p-5">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-coral">Flags</div>
            <h3 className="mt-2 text-xl font-semibold text-navy">Recommended action</h3>
            <div className="mt-5 flex flex-wrap gap-2">
              {task.flags.length ? (
                task.flags.map((flag) => (
                  <span key={flag} className="badge bg-rose-100 text-rose-700">
                    {flag}
                  </span>
                ))
              ) : (
                <span className="text-sm text-slate">No flags recorded for this task.</span>
              )}
            </div>
            <p className="mt-4 text-sm text-slate">
              {task.results_summary || "No AI-generated follow-up summary has been stored yet."}
            </p>
          </section>
        </aside>
      </section>
    </div>
  );
}
