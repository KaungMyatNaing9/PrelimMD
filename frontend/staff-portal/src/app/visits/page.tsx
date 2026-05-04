"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getPatients, getVisits, type Patient, type ScheduledVisit } from "@/lib/api";

export default function VisitsPage() {
  const [patients, setPatients] = useState<Record<string, Patient>>({});
  const [visits, setVisits] = useState<ScheduledVisit[]>([]);
  const [filter, setFilter] = useState<"today" | "upcoming" | "all">("today");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    return Promise.all([getPatients(), getVisits()])
      .then(([patientData, visitData]) => {
        setPatients(Object.fromEntries(patientData.map((patient) => [patient.patient_id, patient])));
        setVisits(visitData);
      });
  }, []);

  useEffect(() => {
    let cancelled = false;
    void load().finally(() => {
      if (!cancelled) setLoading(false);
    });
    const interval = window.setInterval(() => void load(), 15000);
    const onFocus = () => void load();
    window.addEventListener("focus", onFocus);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [load]);

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const filtered = useMemo(() => {
    const sorted = [...visits].sort((a, b) => a.visit_date.localeCompare(b.visit_date) || a.visit_time.localeCompare(b.visit_time));
    if (filter === "today") return sorted.filter((visit) => visit.visit_date === today);
    if (filter === "upcoming") return sorted.filter((visit) => visit.visit_date >= today);
    return sorted;
  }, [filter, today, visits]);

  return (
    <div className="space-y-6">
      <section className="card p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Scheduled Visits</div>
            <h2 className="mt-2 text-2xl font-semibold text-navy">Visit queue</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {(["today", "upcoming", "all"] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setFilter(item)}
                className={filter === item ? "btn-primary" : "btn-secondary"}
              >
                {item[0].toUpperCase() + item.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate">
              <tr>
                <th className="px-5 py-3 font-semibold">Patient</th>
                <th className="px-5 py-3 font-semibold">Date</th>
                <th className="px-5 py-3 font-semibold">Department</th>
                <th className="px-5 py-3 font-semibold">Provider</th>
                <th className="px-5 py-3 font-semibold">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-slate">Loading visits...</td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-slate">No visits found for this filter.</td>
                </tr>
              ) : (
                filtered.map((visit) => {
                  const patient = patients[visit.patient_id];
                  return (
                    <tr key={visit.visit_id} className="border-t border-slate-100">
                      <td className="px-5 py-4 font-semibold text-navy">
                        {patient ? `${patient.first_name} ${patient.last_name}` : visit.patient_id}
                      </td>
                      <td className="px-5 py-4 text-slate">{visit.visit_date} · {visit.visit_time}</td>
                      <td className="px-5 py-4 text-slate">{visit.department}</td>
                      <td className="px-5 py-4 text-slate">{visit.provider_name}</td>
                      <td className="px-5 py-4">
                        <Link href={`/visits/${visit.visit_id}`} className="btn-secondary">
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
