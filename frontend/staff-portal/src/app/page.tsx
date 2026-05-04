"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getFollowUpTasks,
  getIntakeOverview,
  getIntakeSessions,
  getPatients,
  getVisits,
  type FollowUpTask,
  type IntakeOverview,
  type IntakeSession,
  type Patient,
  type ScheduledVisit,
} from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  Pending: "bg-slate-100 text-slate-700",
  "Call Scheduled": "bg-sky-100 text-sky-700",
  "Call Complete": "bg-teal-100 text-teal-700",
  Ready: "bg-emerald-100 text-emerald-700",
  Incomplete: "bg-amber-100 text-amber-800",
};

function sameDay(date: string, today: string) {
  return date === today;
}

function callStatusForVisit(visit: ScheduledVisit, overview?: IntakeOverview, session?: IntakeSession) {
  if (visit.status === "checked_in" || visit.status === "completed") return "Ready";
  if (overview && overview.remaining_fields === 0) return "Ready";
  if (session?.status === "completed") return "Call Complete";
  if (session) return "Call Scheduled";
  if (overview && overview.total_forms > 0) return "Incomplete";
  return "Pending";
}

function statCard(title: string, value: number, note: string, icon: string, tone: string) {
  return (
    <article className="stat-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-slate">{title}</div>
          <div className="mt-2 text-3xl font-semibold tracking-tight text-navy">{value}</div>
          <p className="mt-2 text-sm text-slate">{note}</p>
        </div>
        <div className={`flex h-12 w-12 items-center justify-center rounded-2xl ${tone} text-lg`}>
          {icon}
        </div>
      </div>
    </article>
  );
}

export default function DashboardPage() {
  const [patients, setPatients] = useState<Record<string, Patient>>({});
  const [visits, setVisits] = useState<ScheduledVisit[]>([]);
  const [sessions, setSessions] = useState<IntakeSession[]>([]);
  const [tasks, setTasks] = useState<FollowUpTask[]>([]);
  const [overviews, setOverviews] = useState<Record<string, IntakeOverview>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (cancelledRef?: { current: boolean }) => {
    try {
      const [patientData, visitData, sessionData, taskData] = await Promise.all([
        getPatients(),
        getVisits(),
        getIntakeSessions(),
        getFollowUpTasks(),
      ]);

      if (cancelledRef?.current) return;

      setPatients(Object.fromEntries(patientData.map((patient) => [patient.patient_id, patient])));
      setVisits(visitData);
      setSessions(sessionData);
      setTasks(taskData);

      const overviewPairs = await Promise.all(
        visitData.map(async (visit) => {
          try {
            return [visit.visit_id, await getIntakeOverview(visit.visit_id)] as const;
          } catch {
            return null;
          }
        })
      );

      if (cancelledRef?.current) return;

      setOverviews(
        Object.fromEntries(
          overviewPairs.filter((pair): pair is readonly [string, IntakeOverview] => Boolean(pair))
        )
      );
      setError("");
    } catch {
      if (!cancelledRef?.current) setError("Could not load portal data from the backend.");
    } finally {
      if (!cancelledRef?.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const cancelledRef = { current: false };
    void load(cancelledRef);
    const interval = window.setInterval(() => void load(cancelledRef), 15000);
    const onFocus = () => void load(cancelledRef);
    window.addEventListener("focus", onFocus);
    return () => {
      cancelledRef.current = true;
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [load]);

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const todayVisits = useMemo(
    () =>
      [...visits]
        .filter((visit) => sameDay(visit.visit_date, today) && visit.status !== "cancelled")
        .sort((a, b) => a.visit_time.localeCompare(b.visit_time)),
    [today, visits]
  );

  const sessionsByVisit = useMemo(
    () =>
      Object.fromEntries(
        sessions
          .filter((session) => session.visit_id)
          .map((session) => [session.visit_id as string, session])
      ),
    [sessions]
  );

  const callsPending = useMemo(
    () => sessions.filter((session) => session.status === "in_progress").length,
    [sessions]
  );

  const formsComplete = useMemo(
    () => Object.values(overviews).filter((overview) => overview.remaining_fields === 0).length,
    [overviews]
  );

  const readyForCheckin = useMemo(
    () =>
      todayVisits.filter((visit) => {
        const overview = overviews[visit.visit_id];
        return visit.status === "checked_in" || overview?.completion_percent === 100;
      }).length,
    [overviews, todayVisits]
  );

  const recentResults = useMemo(
    () =>
      [...tasks]
        .filter((task) => task.status === "completed" || task.flags.length > 0 || task.results_summary)
        .sort((a, b) => b.scheduled_at.localeCompare(a.scheduled_at))
        .slice(0, 5),
    [tasks]
  );

  const riskAlerts = useMemo(
    () =>
      [...tasks]
        .filter((task) => task.flags.length > 0)
        .sort((a, b) => b.scheduled_at.localeCompare(a.scheduled_at))
        .slice(0, 5),
    [tasks]
  );

  return (
    <div className="space-y-6">
      {error ? (
        <section className="card p-5 text-sm text-coral">{error}</section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {statCard("Scheduled Today", loading ? 0 : todayVisits.length, "Patients on today’s intake list.", "🗓", "bg-slate-100 text-slate-700")}
        {statCard("Calls Pending", loading ? 0 : callsPending, "Intake calls currently in progress.", "📞", "bg-sky-100 text-sky-700")}
        {statCard("Forms Complete", loading ? 0 : formsComplete, "Visits with no remaining intake fields.", "✓", "bg-teal-100 text-teal-700")}
        {statCard("Ready for Check-in", loading ? 0 : readyForCheckin, "Patients who can move straight to kiosk review.", "⟶", "bg-emerald-100 text-emerald-700")}
      </section>

      <section className="card overflow-hidden">
        <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-xl font-semibold text-navy">Today&apos;s Patients</h2>
            <p className="mt-1 text-sm text-slate">Open the intake workspace to assign forms, prefill, or schedule an AI call.</p>
          </div>
          <Link href="/patients" className="btn-secondary">
            Manage patients
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate">
              <tr>
                <th className="px-5 py-3 font-semibold">Patient Name</th>
                <th className="px-5 py-3 font-semibold">Appointment Time</th>
                <th className="px-5 py-3 font-semibold">Department</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-slate">Loading today&apos;s schedule...</td>
                </tr>
              ) : todayVisits.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-slate">No visits scheduled for today.</td>
                </tr>
              ) : (
                todayVisits.map((visit) => {
                  const patient = patients[visit.patient_id];
                  const overview = overviews[visit.visit_id];
                  const status = callStatusForVisit(visit, overview, sessionsByVisit[visit.visit_id]);
                  return (
                    <tr key={visit.visit_id} className="border-t border-slate-100">
                      <td className="px-5 py-4">
                        <div className="font-semibold text-navy">
                          {patient ? `${patient.first_name} ${patient.last_name}` : visit.patient_id}
                        </div>
                        <div className="mt-1 text-xs text-slate">{visit.reason || "Reason not entered"}</div>
                      </td>
                      <td className="px-5 py-4 text-slate">{visit.visit_time}</td>
                      <td className="px-5 py-4 text-slate">{visit.department}</td>
                      <td className="px-5 py-4">
                        <span className={`badge ${STATUS_STYLES[status] ?? STATUS_STYLES.Pending}`}>{status}</span>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap gap-2">
                          <Link href={`/visits/${visit.visit_id}`} className="btn-secondary">
                            Select Forms
                          </Link>
                          <Link href={`/calls?visit_id=${visit.visit_id}`} className="btn-primary">
                            Schedule Call
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,1fr)]">
        <div className="card p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-navy">Recent Call Results</h2>
              <p className="mt-1 text-sm text-slate">Doctor-facing summary of completed or flagged follow-up tasks.</p>
            </div>
            <Link href="/risk-alerts" className="btn-secondary">
              Open alerts
            </Link>
          </div>

          <div className="mt-5 space-y-4">
            {loading ? (
              <div className="text-sm text-slate">Loading results...</div>
            ) : recentResults.length === 0 ? (
              <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate">No completed or flagged follow-up calls yet.</div>
            ) : (
              recentResults.map((task) => {
                const patient = patients[task.patient_id];
                return (
                  <div key={task.task_id} className="rounded-3xl border border-slate-200 bg-white p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="font-semibold text-navy">
                          {patient ? `${patient.first_name} ${patient.last_name}` : task.patient_id}
                        </div>
                        <div className="mt-1 text-sm text-slate">
                          {task.scheduled_at.slice(0, 10)} · {task.questions.length} questions
                        </div>
                      </div>
                      <span className={`badge ${task.flags.length ? "bg-rose-100 text-rose-700" : "bg-teal-100 text-teal-700"}`}>
                        {task.flags.length ? `${task.flags.length} alert${task.flags.length === 1 ? "" : "s"}` : task.status}
                      </span>
                    </div>
                    <p className="mt-3 text-sm text-slate">
                      {task.results_summary || "Call record exists, but no AI summary has been stored yet."}
                    </p>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <aside className="card p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-navy">Risk Alerts</h2>
              <p className="mt-1 text-sm text-slate">Patients whose follow-up tasks contain flags for review.</p>
            </div>
          </div>

          <div className="mt-5 space-y-4">
            {loading ? (
              <div className="text-sm text-slate">Loading alerts...</div>
            ) : riskAlerts.length === 0 ? (
              <div className="rounded-2xl bg-teal-soft p-4 text-sm text-slate">No follow-up flags are currently stored in the database.</div>
            ) : (
              riskAlerts.map((task) => {
                const patient = patients[task.patient_id];
                return (
                  <div key={task.task_id} className="rounded-3xl border border-rose-200 bg-rose-50 p-4">
                    <div className="font-semibold text-navy">
                      {patient ? `${patient.first_name} ${patient.last_name}` : task.patient_id}
                    </div>
                    <div className="mt-1 text-sm text-slate">
                      Last scheduled {task.scheduled_at.slice(0, 10)}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {task.flags.map((flag) => (
                        <span key={flag} className="badge bg-white text-rose-700">
                          {flag}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </aside>
      </section>
    </div>
  );
}
