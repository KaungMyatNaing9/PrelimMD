"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  getFollowUpTasks,
  getPatients,
  getVisits,
  type FollowUpTask,
  type Patient,
  type ScheduledVisit,
} from "@/lib/api";

const TODAY = new Date().toISOString().slice(0, 10);

function deptBadge(dept: string) {
  const map: Record<string, string> = {
    Cardiology: "badge badge-cardiology",
    Neurology: "badge badge-neurology",
    Orthopedics: "badge badge-orthopedics",
    "General Practice": "badge badge-general",
  };

  return map[dept] ?? "badge badge-general";
}

function initials(first?: string, last?: string) {
  return `${first?.[0] ?? ""}${last?.[0] ?? ""}` || "PT";
}

export default function DashboardPage() {
  const [visits, setVisits] = useState<ScheduledVisit[]>([]);
  const [patients, setPatients] = useState<Record<string, Patient>>({});
  const [tasks, setTasks] = useState<FollowUpTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getVisits(), getPatients(), getFollowUpTasks()])
      .then(([visitData, patientData, taskData]) => {
        setVisits(visitData);
        setPatients(Object.fromEntries(patientData.map((pt) => [pt.patient_id, pt])));
        setTasks(taskData);
      })
      .catch(() => {
        setError("Could not reach the backend. Make sure the server is running on port 8000.");
      })
      .finally(() => setLoading(false));
  }, []);

  const todayVisits = useMemo(
    () =>
      visits
        .filter((visit) => visit.visit_date === TODAY && visit.status === "scheduled")
        .sort((a, b) => a.visit_time.localeCompare(b.visit_time)),
    [visits]
  );

  const upcomingVisits = useMemo(
    () =>
      visits
        .filter((visit) => visit.visit_date > TODAY && visit.status === "scheduled")
        .sort(
          (a, b) =>
            a.visit_date.localeCompare(b.visit_date) || a.visit_time.localeCompare(b.visit_time)
        )
        .slice(0, 6),
    [visits]
  );

  const pendingTasks = useMemo(
    () => tasks.filter((task) => task.status === "scheduled"),
    [tasks]
  );

  const readyPatients = useMemo(
    () => todayVisits.filter((visit) => visit.department !== "Cardiology").length,
    [todayVisits]
  );

  return (
    <div className="page">
      <section className="page-hero">
        <div>
          <div className="eyebrow">Shift Snapshot</div>
          <h2>Today&apos;s intake queue is organized and ready for action.</h2>
          <p>
            Review scheduled visits, open patient workflows, and move directly into prefill or
            follow-up outreach from the same clinical workspace.
          </p>
        </div>
        <div className="page-hero-actions">
          <Link href="/patients" className="btn btn-secondary">
            Open patient roster
          </Link>
          <Link href="/followups" className="btn btn-primary">
            Review follow-up calls
          </Link>
        </div>
      </section>

      {error ? (
        <div className="panel">
          <div className="helper-note">{error}</div>
        </div>
      ) : null}

      <section className="metric-grid">
        <article className="metric-card soft-blue">
          <div className="metric-kicker">Scheduled Today</div>
          <div className="metric-value">{loading ? "-" : todayVisits.length}</div>
          <div className="metric-note">Current same-day appointments waiting on intake review.</div>
        </article>
        <article className="metric-card soft-amber">
          <div className="metric-kicker">Calls Pending</div>
          <div className="metric-value">{loading ? "-" : pendingTasks.length}</div>
          <div className="metric-note">Post-discharge outreach still queued for staff follow-through.</div>
        </article>
        <article className="metric-card soft-teal">
          <div className="metric-kicker">Upcoming Visits</div>
          <div className="metric-value">{loading ? "-" : upcomingVisits.length}</div>
          <div className="metric-note">The next six scheduled visits across the active roster.</div>
        </article>
        <article className="metric-card soft-green">
          <div className="metric-kicker">Ready Flow</div>
          <div className="metric-value">{loading ? "-" : readyPatients}</div>
          <div className="metric-note">Patients likely ready to move into kiosk review and consent.</div>
        </article>
      </section>

      <section className="split-grid">
        <div className="table-card">
          <div className="panel-header" style={{ padding: "1.2rem 1.25rem 0" }}>
            <div>
              <div className="eyebrow">Today</div>
              <h3>
                {new Date().toLocaleDateString("en-US", {
                  weekday: "long",
                  month: "long",
                  day: "numeric",
                })}
              </h3>
              <div className="panel-subtext">
                Open any patient to assign forms, run prefill, or launch the kiosk flow.
              </div>
            </div>
            <Link href="/patients" className="btn btn-secondary btn-sm">
              All patients
            </Link>
          </div>

          <div className="visit-list" style={{ padding: "0 1.25rem 1.25rem" }}>
            {loading ? (
              <div className="loading">Loading schedule...</div>
            ) : todayVisits.length === 0 ? (
              <div className="empty">No visits scheduled for today.</div>
            ) : (
              todayVisits.map((visit) => {
                const patient = patients[visit.patient_id];
                return (
                  <Link key={visit.visit_id} href={`/visits/${visit.visit_id}`} style={{ display: "contents" }}>
                    <div className="visit-row">
                      <div className="visit-time">
                        <span>{visit.visit_time}</span>
                        <span className="visit-time-sub">Today</span>
                      </div>
                      <div className="patient-cell">
                        <div className="patient-avatar">
                          {initials(patient?.first_name, patient?.last_name)}
                        </div>
                        <div>
                          <div className="visit-name">
                            {patient ? `${patient.first_name} ${patient.last_name}` : visit.patient_id}
                          </div>
                          <div className="visit-meta">
                            <strong>{visit.reason}</strong> · {visit.provider_name}
                          </div>
                        </div>
                      </div>
                      <span className={deptBadge(visit.department)}>{visit.department}</span>
                      <span className="badge badge-scheduled">Scheduled</span>
                    </div>
                  </Link>
                );
              })
            )}
          </div>
        </div>

        <div className="stack-list">
          <section className="action-card">
            <div className="panel-header">
              <div>
                <div className="eyebrow">Action Required</div>
                <h3>Pending Follow-Up Calls</h3>
              </div>
              <Link href="/followups" className="btn btn-secondary btn-sm">
                View all
              </Link>
            </div>

            <div className="stack-list">
              {loading ? (
                <div className="loading">Loading follow-ups...</div>
              ) : pendingTasks.length === 0 ? (
                <div className="empty">No pending follow-up tasks.</div>
              ) : (
                pendingTasks.slice(0, 4).map((task) => {
                  const patient = patients[task.patient_id];
                  const date = new Date(task.scheduled_at);
                  return (
                    <Link key={task.task_id} href={`/followups/${task.task_id}`} style={{ display: "contents" }}>
                      <div className="stack-row">
                        <div>
                          <div className="visit-name">
                            {patient ? `${patient.first_name} ${patient.last_name}` : task.patient_id}
                          </div>
                          <div className="visit-meta">
                            {task.questions.length} questions ·{" "}
                            {date.toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                          </div>
                        </div>
                        <span className="badge badge-assigned">Pending</span>
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </section>

          <section className="action-card">
            <div className="eyebrow">Preview Queue</div>
            <h3>Upcoming Visits</h3>
            <p className="helper-text" style={{ marginTop: "0.45rem", marginBottom: "1rem" }}>
              A quick look at the next scheduled patients helps staff spot workload and prep needs.
            </p>
            <div className="stack-list">
              {loading ? (
                <div className="loading">Loading upcoming visits...</div>
              ) : upcomingVisits.length === 0 ? (
                <div className="empty">No upcoming visits found.</div>
              ) : (
                upcomingVisits.map((visit) => {
                  const patient = patients[visit.patient_id];
                  return (
                    <Link key={visit.visit_id} href={`/visits/${visit.visit_id}`} style={{ display: "contents" }}>
                      <div className="stack-row">
                        <div>
                          <div className="visit-name">
                            {patient ? `${patient.first_name} ${patient.last_name}` : visit.patient_id}
                          </div>
                          <div className="visit-meta">
                            {visit.visit_date} at {visit.visit_time} · {visit.department}
                          </div>
                        </div>
                        <span className={deptBadge(visit.department)}>{visit.department}</span>
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}
