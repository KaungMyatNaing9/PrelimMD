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

type IntakeProgressRow = {
  visit: ScheduledVisit;
  patient?: Patient;
  overview?: IntakeOverview;
  latestSession?: IntakeSession;
};

export default function CallsPage() {
  const [highlightedVisitId, setHighlightedVisitId] = useState<string | null>(null);
  const [rows, setRows] = useState<IntakeProgressRow[]>([]);
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

      const patientsById = Object.fromEntries(patientData.map((patient) => [patient.patient_id, patient]));
      const visitsById = Object.fromEntries(visitData.map((visit) => [visit.visit_id, visit]));
      const latestSessionByVisit = new Map<string, IntakeSession>();

      for (const session of sessionData) {
        if (!session.visit_id) continue;
        const existing = latestSessionByVisit.get(session.visit_id);
        if (!existing || session.created_at > existing.created_at) {
          latestSessionByVisit.set(session.visit_id, session);
        }
      }

      const relevantVisitIds = new Set<string>([
        ...Array.from(latestSessionByVisit.keys()),
        ...visitData
          .filter((visit) => visit.status === "checked_in")
          .map((visit) => visit.visit_id),
      ]);

      if (highlightedVisitId) {
        relevantVisitIds.add(highlightedVisitId);
      }

      const overviewPairs = await Promise.all(
        Array.from(relevantVisitIds).map(async (visitId) => {
          try {
            return [visitId, await getIntakeOverview(visitId)] as const;
          } catch {
            return null;
          }
        })
      );

      if (cancelled) return;

      const overviewByVisit = Object.fromEntries(
        overviewPairs.filter((pair): pair is readonly [string, IntakeOverview] => Boolean(pair))
      );

      const builtRows: IntakeProgressRow[] = [];
      for (const visitId of Array.from(relevantVisitIds)) {
        const visit = visitsById[visitId];
        if (!visit) continue;
        builtRows.push({
          visit,
          patient: patientsById[visit.patient_id],
          overview: overviewByVisit[visitId],
          latestSession: latestSessionByVisit.get(visitId),
        });
      }
      builtRows.sort((a, b) => `${b.visit.visit_date} ${b.visit.visit_time}`.localeCompare(`${a.visit.visit_date} ${a.visit.visit_time}`));

      setRows(builtRows);
    }

    load().finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [highlightedVisitId]);

  const filteredRows = useMemo(() => {
    if (!highlightedVisitId) return rows;
    return rows.filter((row) => row.visit.visit_id === highlightedVisitId);
  }, [highlightedVisitId, rows]);

  return (
    <div className="space-y-6">
      <section className="card p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Visit Intake Status</div>
            <h2 className="mt-2 text-2xl font-semibold text-navy">One row per scheduled visit</h2>
            <p className="mt-2 text-sm text-slate">This view shows the latest intake state for each visit instead of listing duplicate session attempts.</p>
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
                <th className="px-5 py-3 font-semibold">EHR Status</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold">Kiosk Follow-up</th>
                <th className="px-5 py-3 font-semibold">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-slate">Loading intake progress...</td>
                </tr>
              ) : filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-slate">No intake activity has been recorded yet.</td>
                </tr>
              ) : (
                filteredRows.map((row) => {
                  const displayStatus = row.visit.status === "checked_in"
                    ? "checked in"
                    : row.latestSession?.status === "completed"
                      ? "intake complete"
                      : row.latestSession
                        ? "intake started"
                        : "assigned";
                  const filled = row.overview?.filled_fields ?? 0;
                  const total = row.overview?.total_fields ?? 0;

                  return (
                    <tr
                      key={row.visit.visit_id}
                      className={`border-t border-slate-100 ${row.visit.visit_id === highlightedVisitId ? "bg-teal-soft/40" : ""}`}
                    >
                      <td className="px-5 py-4">
                        <div className="font-semibold text-navy">
                          {row.patient ? `${row.patient.first_name} ${row.patient.last_name}` : row.visit.patient_id}
                        </div>
                        <div className="mt-1 text-xs text-slate">{row.patient?.phone || "No phone on file"}</div>
                      </td>
                      <td className="px-5 py-4 text-slate">
                        {row.visit.visit_date} · {row.visit.visit_time} · {row.visit.department}
                      </td>
                      <td className="px-5 py-4 text-slate">
                        {total ? `${filled}/${total} fields known` : "No assigned forms"}
                      </td>
                      <td className="px-5 py-4">
                        <span className={`badge ${row.visit.status === "checked_in" || row.latestSession?.status === "completed" ? "bg-teal-100 text-teal-700" : "bg-sky-100 text-sky-700"}`}>
                          {displayStatus}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-slate">{row.overview?.remaining_fields ?? 0} remaining fields</td>
                      <td className="px-5 py-4">
                        <Link href={`/visits/${row.visit.visit_id}`} className="btn-secondary">
                          Open Workspace
                        </Link>
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
