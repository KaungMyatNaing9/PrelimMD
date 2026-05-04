"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getFollowUpTasks, getPatients, getVisits, type FollowUpTask, type Patient, type ScheduledVisit } from "@/lib/api";

function severity(flags: string[]) {
  if (flags.length >= 2) return { label: "High", className: "bg-rose-100 text-rose-700" };
  if (flags.length === 1) return { label: "Medium", className: "bg-amber-100 text-amber-800" };
  return { label: "Low", className: "bg-slate-100 text-slate-700" };
}

export default function RiskAlertsPage() {
  const [tasks, setTasks] = useState<FollowUpTask[]>([]);
  const [patients, setPatients] = useState<Record<string, Patient>>({});
  const [visits, setVisits] = useState<Record<string, ScheduledVisit>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getFollowUpTasks(), getPatients(), getVisits()])
      .then(([taskData, patientData, visitData]) => {
        setTasks(taskData);
        setPatients(Object.fromEntries(patientData.map((patient) => [patient.patient_id, patient])));
        setVisits(Object.fromEntries(visitData.map((visit) => [visit.visit_id, visit])));
      })
      .finally(() => setLoading(false));
  }, []);

  const flaggedTasks = useMemo(
    () => [...tasks].filter((task) => task.flags.length > 0).sort((a, b) => b.scheduled_at.localeCompare(a.scheduled_at)),
    [tasks]
  );

  return (
    <div className="space-y-6">
      <section className="card p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-coral">Doctor Review</div>
            <h2 className="mt-2 text-2xl font-semibold text-navy">Risk alerts</h2>
            <p className="mt-2 text-sm text-slate">This view shows only follow-up tasks with stored backend flags.</p>
          </div>
          <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
            {loading ? "Loading alerts..." : `${flaggedTasks.length} patients require attention`}
          </div>
        </div>
      </section>

      <section className="space-y-4">
        {loading ? (
          <div className="card p-5 text-sm text-slate">Loading risk alerts...</div>
        ) : flaggedTasks.length === 0 ? (
          <div className="card p-5 text-sm text-slate">No flagged follow-up calls are stored yet.</div>
        ) : (
          flaggedTasks.map((task) => {
            const patient = patients[task.patient_id];
            const visit = visits[task.visit_id];
            const level = severity(task.flags);
            return (
              <article key={task.task_id} className="card p-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="text-xl font-semibold text-navy">
                        {patient ? `${patient.first_name} ${patient.last_name}` : task.patient_id}
                      </h3>
                      <span className={`badge ${level.className}`}>{level.label}</span>
                    </div>
                    <div className="mt-2 text-sm text-slate">
                      {visit ? `${visit.department} · ${visit.reason || "No reason entered"}` : "Visit details unavailable"}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {task.flags.map((flag) => (
                        <span key={flag} className="badge bg-white text-rose-700 ring-1 ring-inset ring-rose-200">
                          {flag}
                        </span>
                      ))}
                    </div>
                    <p className="mt-4 text-sm text-slate">
                      {task.results_summary || "No AI summary has been persisted for this follow-up task yet."}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link href={`/followups/${task.task_id}`} className="btn-secondary">
                      Review Call
                    </Link>
                    {visit ? (
                      <Link href={`/visits/${visit.visit_id}`} className="btn-primary">
                        Open Patient
                      </Link>
                    ) : null}
                  </div>
                </div>
              </article>
            );
          })
        )}
      </section>
    </div>
  );
}
