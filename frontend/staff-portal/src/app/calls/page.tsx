"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
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

export default function CallsPage() {
  const [highlightedVisitId, setHighlightedVisitId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<IntakeSession[]>([]);
  const [patients, setPatients] = useState<Record<string, Patient>>({});
  const [visits, setVisits] = useState<Record<string, ScheduledVisit>>({});
  const [overviews, setOverviews] = useState<Record<string, IntakeOverview>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setHighlightedVisitId(new URLSearchParams(window.location.search).get("visit_id"));
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const [sessionData, patientData, visitData] = await Promise.all([
        getIntakeSessions(),
        getPatients(),
        getVisits(),
      ]);

      if (cancelled) return;

      setSessions(sessionData.sort((a, b) => b.created_at.localeCompare(a.created_at)));
      setPatients(Object.fromEntries(patientData.map((patient) => [patient.patient_id, patient])));
      setVisits(Object.fromEntries(visitData.map((visit) => [visit.visit_id, visit])));

      const pairs = await Promise.all(
        visitData.map(async (visit) => {
          try {
            return [visit.visit_id, await getIntakeOverview(visit.visit_id)] as const;
          } catch {
            return null;
          }
        })
      );

      if (cancelled) return;

      setOverviews(Object.fromEntries(pairs.filter((pair): pair is readonly [string, IntakeOverview] => Boolean(pair))));
    }

    load().finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const filteredSessions = useMemo(() => {
    if (!highlightedVisitId) return sessions;
    return sessions.filter((session) => session.visit_id === highlightedVisitId);
  }, [highlightedVisitId, sessions]);

  return (
    <div className="space-y-6">
      <section className="card p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Upcoming Intake Calls</div>
            <h2 className="mt-2 text-2xl font-semibold text-navy">Call queue and completion status</h2>
            <p className="mt-2 text-sm text-slate">This page is backed by stored intake sessions and visit readiness summaries.</p>
          </div>
          {highlightedVisitId ? (
            <Link href="/calls" className="btn-secondary">
              Clear visit filter
            </Link>
          ) : null}
        </div>
      </section>

      <section className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate">
              <tr>
                <th className="px-5 py-3 font-semibold">Patient</th>
                <th className="px-5 py-3 font-semibold">Visit</th>
                <th className="px-5 py-3 font-semibold">Questions</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold">Kiosk Follow-up</th>
                <th className="px-5 py-3 font-semibold">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-slate">Loading intake sessions...</td>
                </tr>
              ) : filteredSessions.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-slate">No intake call sessions found.</td>
                </tr>
              ) : (
                filteredSessions.map((session) => {
                  const patient = patients[session.patient_id];
                  const visit = session.visit_id ? visits[session.visit_id] : undefined;
                  const overview = session.visit_id ? overviews[session.visit_id] : undefined;
                  const answered = Object.keys(session.collected_answers).length;
                  const total = session.conversation.filter((turn) => turn.role === "ai").length || overview?.call_remaining_fields || 0;
                  return (
                    <tr
                      key={session.session_id}
                      className={`border-t border-slate-100 ${session.visit_id === highlightedVisitId ? "bg-teal-soft/40" : ""}`}
                    >
                      <td className="px-5 py-4">
                        <div className="font-semibold text-navy">
                          {patient ? `${patient.first_name} ${patient.last_name}` : session.patient_id}
                        </div>
                        <div className="mt-1 text-xs text-slate">{patient?.phone || "No phone on file"}</div>
                      </td>
                      <td className="px-5 py-4 text-slate">
                        {visit ? `${visit.visit_date} · ${visit.visit_time} · ${visit.department}` : session.visit_id || "No visit linked"}
                      </td>
                      <td className="px-5 py-4 text-slate">Answered {answered}/{total || answered}</td>
                      <td className="px-5 py-4">
                        <span className={`badge ${session.status === "completed" ? "bg-teal-100 text-teal-700" : "bg-sky-100 text-sky-700"}`}>
                          {session.status.replace("_", " ")}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-slate">{overview?.remaining_fields ?? 0} remaining fields</td>
                      <td className="px-5 py-4">
                        {visit ? (
                          <Link href={`/visits/${visit.visit_id}`} className="btn-secondary">
                            Open Workspace
                          </Link>
                        ) : (
                          <span className="text-slate">No linked visit</span>
                        )}
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
