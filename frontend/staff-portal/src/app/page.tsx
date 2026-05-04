"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getIntakeOverview,
  getIntakeSessions,
  getPatients,
  getVisits,
  type IntakeOverview,
  type IntakeSession,
  type Patient,
  type ScheduledVisit,
} from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  Pending: "bg-slate-100 text-slate-700",
  "Intake Started": "bg-sky-100 text-sky-700",
  "Intake Complete": "bg-teal-100 text-teal-700",
  Ready: "bg-emerald-100 text-emerald-700",
  "Checked In": "bg-emerald-100 text-emerald-700",
  Incomplete: "bg-amber-100 text-amber-800",
};

function sameDay(date: string, today: string) {
  return date === today;
}

function callStatusForVisit(visit: ScheduledVisit, overview?: IntakeOverview, session?: IntakeSession) {
  if (visit.status === "checked_in") return "Checked In";
  if (visit.status === "completed") return "Ready";
  if (overview && overview.remaining_fields === 0) return "Ready";
  if (session?.status === "completed") return "Intake Complete";
  if (session) return "Intake Started";
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
  const [overviews, setOverviews] = useState<Record<string, IntakeOverview>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (cancelledRef?: { current: boolean }) => {
    try {
      const [patientData, visitData, sessionData] = await Promise.all([
        getPatients(),
        getVisits(),
        getIntakeSessions(),
      ]);

      if (cancelledRef?.current) return;

      setPatients(Object.fromEntries(patientData.map((patient) => [patient.patient_id, patient])));
      setVisits(visitData);
      setSessions(sessionData);

      const relevantVisitIds = new Set([
        ...visitData
          .filter((visit) => visit.status === "checked_in" || sameDay(visit.visit_date, new Date().toISOString().slice(0, 10)))
          .map((visit) => visit.visit_id),
        ...sessionData
          .map((session) => session.visit_id)
          .filter((visitId): visitId is string => Boolean(visitId)),
      ]);

      const overviewPairs = await Promise.all(
        Array.from(relevantVisitIds).map(async (visitId) => {
          try {
            return [visitId, await getIntakeOverview(visitId)] as const;
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

  return (
    <div className="space-y-6">
      {error ? (
        <section className="card p-5 text-sm text-coral">{error}</section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {statCard("Scheduled Today", loading ? 0 : todayVisits.length, "Patients on today’s intake list.", "🗓", "bg-slate-100 text-slate-700")}
        {statCard("Intake Started", loading ? 0 : callsPending, "Visits with active voice or kiosk intake progress.", "🗣", "bg-sky-100 text-sky-700")}
        {statCard("Forms Complete", loading ? 0 : formsComplete, "Visits with no remaining intake fields.", "✓", "bg-teal-100 text-teal-700")}
        {statCard("Ready for Check-in", loading ? 0 : readyForCheckin, "Patients who can move straight to kiosk review.", "⟶", "bg-emerald-100 text-emerald-700")}
      </section>

      <section className="card overflow-hidden">
        <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-xl font-semibold text-navy">Today&apos;s Patients</h2>
            <p className="mt-1 text-sm text-slate">Open the intake workspace to assign forms, run prefill, or send the patient to kiosk review.</p>
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
                            Intake Progress
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
    </div>
  );
}
