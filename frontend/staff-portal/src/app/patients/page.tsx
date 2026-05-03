"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getPatients, getVisits, type Patient, type ScheduledVisit } from "@/lib/api";

function initials(first?: string, last?: string) {
  return `${first?.[0] ?? ""}${last?.[0] ?? ""}` || "PT";
}

export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [visits, setVisits] = useState<ScheduledVisit[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getPatients(), getVisits()])
      .then(([patientData, visitData]) => {
        setPatients(patientData);
        setVisits(visitData);
      })
      .finally(() => setLoading(false));
  }, []);

  const nextVisit = (patientId: string) =>
    visits
      .filter((visit) => visit.patient_id === patientId && visit.status === "scheduled")
      .sort(
        (a, b) =>
          a.visit_date.localeCompare(b.visit_date) || a.visit_time.localeCompare(b.visit_time)
      )[0];

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) {
      return patients;
    }

    return patients.filter((patient) => {
      return (
        patient.first_name.toLowerCase().includes(q) ||
        patient.last_name.toLowerCase().includes(q) ||
        patient.email?.toLowerCase().includes(q) ||
        patient.phone.includes(q)
      );
    });
  }, [patients, query]);

  return (
    <div className="page">
      <section className="page-hero">
        <div>
          <div className="eyebrow">Registry</div>
          <h2>Patient roster across active departments.</h2>
          <p>
            Search the shared roster, review demographic coverage, and jump straight into the next
            scheduled visit for each patient.
          </p>
        </div>
      </section>

      <section className="table-card">
        <div className="panel-header" style={{ padding: "1.2rem 1.25rem 0" }}>
          <div>
            <h3>All Patients</h3>
            <div className="panel-subtext">{patients.length} patients in the current mock roster.</div>
          </div>
          <div className="search-wrap" style={{ width: "20rem", maxWidth: "100%" }}>
            <span className="search-icon">⌕</span>
            <input
              className="input"
              placeholder="Search name, email, or phone"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </div>

        {loading ? (
          <div className="loading">Loading patients...</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Patient</th>
                <th>DOB</th>
                <th>Gender</th>
                <th>Insurance</th>
                <th>Next Visit</th>
                <th>Phone</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((patient) => {
                const visit = nextVisit(patient.patient_id);
                return (
                  <tr
                    key={patient.patient_id}
                    onClick={() => visit && (window.location.href = `/visits/${visit.visit_id}`)}
                    style={{ cursor: visit ? "pointer" : "default" }}
                  >
                    <td>
                      <div className="patient-cell">
                        <div className="patient-avatar">
                          {initials(patient.first_name, patient.last_name)}
                        </div>
                        <div>
                          <div className="patient-primary">
                            {patient.first_name} {patient.last_name}
                          </div>
                          <div className="patient-secondary">
                            {patient.email || "No email on file"}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="text-soft">{patient.date_of_birth}</td>
                    <td className="text-soft" style={{ textTransform: "capitalize" }}>
                      {patient.gender}
                    </td>
                    <td className="text-soft">{patient.insurance_provider ?? "-"}</td>
                    <td>
                      {visit ? (
                        <Link
                          href={`/visits/${visit.visit_id}`}
                          className="text-link"
                          onClick={(event) => event.stopPropagation()}
                        >
                          {visit.visit_date} · {visit.department}
                        </Link>
                      ) : (
                        <span className="text-soft">None scheduled</span>
                      )}
                    </td>
                    <td className="text-soft">{patient.phone}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {!loading && filtered.length === 0 ? (
          <div className="empty">No patients matched "{query}".</div>
        ) : null}
      </section>
    </div>
  );
}
