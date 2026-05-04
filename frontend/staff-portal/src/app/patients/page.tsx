"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  createPatient,
  createVisit,
  getPatients,
  getVisits,
  type CreatePatientPayload,
  type CreateVisitPayload,
  type Patient,
  type ScheduledVisit,
} from "@/lib/api";

const emptyPatient: CreatePatientPayload = {
  first_name: "",
  last_name: "",
  date_of_birth: "",
  gender: "",
  phone: "",
  email: "",
  address: "",
  insurance_provider: "",
  insurance_id: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
  emergency_contact_relation: "",
};

const defaultVisit: CreateVisitPayload = {
  patient_id: "",
  visit_date: "",
  visit_time: "",
  provider_name: "",
  department: "General",
  reason: "",
  notes: "",
};

function initials(patient: Patient) {
  return `${patient.first_name[0] ?? ""}${patient.last_name[0] ?? ""}` || "PT";
}

export default function PatientsPage() {
  const router = useRouter();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [visits, setVisits] = useState<ScheduledVisit[]>([]);
  const [patientForm, setPatientForm] = useState<CreatePatientPayload>(emptyPatient);
  const [visitForm, setVisitForm] = useState<CreateVisitPayload>(defaultVisit);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<"" | "patient" | "visit">("");
  const [message, setMessage] = useState("");

  async function load() {
    const [patientData, visitData] = await Promise.all([getPatients(), getVisits()]);
    setPatients(patientData);
    setVisits(visitData);
  }

  useEffect(() => {
    load()
      .catch(() => setMessage("Could not load patients from the backend."))
      .finally(() => setLoading(false));
  }, []);

  const filteredPatients = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter((patient) =>
      [
        patient.first_name,
        patient.last_name,
        patient.phone ?? "",
        patient.email ?? "",
        patient.insurance_id ?? "",
      ].some((value) => value.toLowerCase().includes(q))
    );
  }, [patients, query]);

  const nextVisitByPatient = useMemo(() => {
    const sorted = visits
      .filter((visit) => visit.status !== "cancelled")
      .sort((a, b) => a.visit_date.localeCompare(b.visit_date) || a.visit_time.localeCompare(b.visit_time));
    const map: Record<string, ScheduledVisit> = {};
    for (const visit of sorted) {
      if (!map[visit.patient_id]) {
        map[visit.patient_id] = visit;
      }
    }
    return map;
  }, [visits]);

  async function handleCreatePatient(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving("patient");
    setMessage("");
    try {
      const created = await createPatient(patientForm);
      await load();
      setPatientForm(emptyPatient);
      setVisitForm((current) => ({ ...current, patient_id: created.patient_id }));
      setMessage(`Patient ${created.first_name} ${created.last_name} created.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to create patient.");
    } finally {
      setSaving("");
    }
  }

  async function handleScheduleVisit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving("visit");
    setMessage("");
    try {
      const visit = await createVisit(visitForm);
      await load();
      setVisitForm(defaultVisit);
      router.push(`/visits/${visit.visit_id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to schedule visit.");
    } finally {
      setSaving("");
    }
  }

  return (
    <div className="space-y-6">
      {message ? <section className="card p-4 text-sm text-slate">{message}</section> : null}

      <section className="grid gap-6 xl:grid-cols-2">
        <form className="card p-5" onSubmit={handleCreatePatient}>
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Add Patient</div>
            <h2 className="mt-2 text-2xl font-semibold text-navy">Create patient profile</h2>
            <p className="mt-2 text-sm text-slate">New patient records are saved directly to Postgres through the backend.</p>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div>
              <label className="field-label">First Name</label>
              <input className="field-input" value={patientForm.first_name} onChange={(event) => setPatientForm((current) => ({ ...current, first_name: event.target.value }))} required />
            </div>
            <div>
              <label className="field-label">Last Name</label>
              <input className="field-input" value={patientForm.last_name} onChange={(event) => setPatientForm((current) => ({ ...current, last_name: event.target.value }))} required />
            </div>
            <div>
              <label className="field-label">Date of Birth</label>
              <input type="date" className="field-input" value={patientForm.date_of_birth} onChange={(event) => setPatientForm((current) => ({ ...current, date_of_birth: event.target.value }))} required />
            </div>
            <div>
              <label className="field-label">Gender</label>
              <select className="field-input" value={patientForm.gender} onChange={(event) => setPatientForm((current) => ({ ...current, gender: event.target.value }))} required>
                <option value="">Select</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="non-binary">Non-binary</option>
                <option value="prefer_not_to_say">Prefer not to say</option>
              </select>
            </div>
            <div>
              <label className="field-label">Phone</label>
              <input className="field-input" value={patientForm.phone ?? ""} onChange={(event) => setPatientForm((current) => ({ ...current, phone: event.target.value }))} />
            </div>
            <div>
              <label className="field-label">Email</label>
              <input className="field-input" value={patientForm.email ?? ""} onChange={(event) => setPatientForm((current) => ({ ...current, email: event.target.value }))} />
            </div>
            <div className="md:col-span-2">
              <label className="field-label">Address</label>
              <input className="field-input" value={patientForm.address ?? ""} onChange={(event) => setPatientForm((current) => ({ ...current, address: event.target.value }))} />
            </div>
            <div>
              <label className="field-label">Insurance Provider</label>
              <input className="field-input" value={patientForm.insurance_provider ?? ""} onChange={(event) => setPatientForm((current) => ({ ...current, insurance_provider: event.target.value }))} />
            </div>
            <div>
              <label className="field-label">Insurance ID</label>
              <input className="field-input" value={patientForm.insurance_id ?? ""} onChange={(event) => setPatientForm((current) => ({ ...current, insurance_id: event.target.value }))} />
            </div>
          </div>

          <div className="mt-5">
            <button className="btn-primary" disabled={saving === "patient"}>
              {saving === "patient" ? "Creating..." : "Create Patient"}
            </button>
          </div>
        </form>

        <form className="card p-5" onSubmit={handleScheduleVisit}>
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Schedule Visit</div>
            <h2 className="mt-2 text-2xl font-semibold text-navy">Create scheduled appointment</h2>
            <p className="mt-2 text-sm text-slate">After scheduling, the visit workspace opens so forms and pre-visit calls can be assigned.</p>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <label className="field-label">Patient</label>
              <select className="field-input" value={visitForm.patient_id} onChange={(event) => setVisitForm((current) => ({ ...current, patient_id: event.target.value }))} required>
                <option value="">Select patient</option>
                {patients.map((patient) => (
                  <option key={patient.patient_id} value={patient.patient_id}>
                    {patient.first_name} {patient.last_name} · {patient.date_of_birth}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="field-label">Visit Date</label>
              <input type="date" className="field-input" value={visitForm.visit_date} onChange={(event) => setVisitForm((current) => ({ ...current, visit_date: event.target.value }))} required />
            </div>
            <div>
              <label className="field-label">Visit Time</label>
              <input type="time" className="field-input" value={visitForm.visit_time} onChange={(event) => setVisitForm((current) => ({ ...current, visit_time: event.target.value }))} required />
            </div>
            <div>
              <label className="field-label">Provider Name</label>
              <input className="field-input" value={visitForm.provider_name} onChange={(event) => setVisitForm((current) => ({ ...current, provider_name: event.target.value }))} required />
            </div>
            <div>
              <label className="field-label">Department</label>
              <select className="field-input" value={visitForm.department} onChange={(event) => setVisitForm((current) => ({ ...current, department: event.target.value }))} required>
                <option value="General">General</option>
                <option value="Cardiology">Cardiology</option>
                <option value="Orthopedics">Orthopedics</option>
                <option value="Neurology">Neurology</option>
                <option value="Pediatrics">Pediatrics</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="field-label">Reason for Visit</label>
              <input className="field-input" value={visitForm.reason ?? ""} onChange={(event) => setVisitForm((current) => ({ ...current, reason: event.target.value }))} />
            </div>
            <div className="md:col-span-2">
              <label className="field-label">Notes</label>
              <textarea className="field-input min-h-28" value={visitForm.notes ?? ""} onChange={(event) => setVisitForm((current) => ({ ...current, notes: event.target.value }))} />
            </div>
          </div>

          <div className="mt-5">
            <button className="btn-primary" disabled={saving === "visit"}>
              {saving === "visit" ? "Scheduling..." : "Create Visit"}
            </button>
          </div>
        </form>
      </section>

      <section className="card overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-slate-200 px-5 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-navy">Patient Roster</h2>
            <p className="mt-1 text-sm text-slate">Every row is backed by the current database state.</p>
          </div>
          <div className="w-full max-w-sm">
            <input className="field-input" placeholder="Search name, phone, email, insurance" value={query} onChange={(event) => setQuery(event.target.value)} />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate">
              <tr>
                <th className="px-5 py-3 font-semibold">Patient</th>
                <th className="px-5 py-3 font-semibold">DOB</th>
                <th className="px-5 py-3 font-semibold">Insurance</th>
                <th className="px-5 py-3 font-semibold">Next Visit</th>
                <th className="px-5 py-3 font-semibold">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-slate">Loading patients...</td>
                </tr>
              ) : filteredPatients.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-slate">No patient records match the current search.</td>
                </tr>
              ) : (
                filteredPatients.map((patient) => {
                  const visit = nextVisitByPatient[patient.patient_id];
                  return (
                    <tr key={patient.patient_id} className="border-t border-slate-100">
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-teal-soft font-semibold text-teal">
                            {initials(patient)}
                          </div>
                          <div>
                            <div className="font-semibold text-navy">{patient.first_name} {patient.last_name}</div>
                            <div className="mt-1 text-xs text-slate">{patient.phone || patient.email || "No contact info"}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-slate">{patient.date_of_birth}</td>
                      <td className="px-5 py-4 text-slate">{patient.insurance_provider || "-"}</td>
                      <td className="px-5 py-4 text-slate">
                        {visit ? `${visit.visit_date} · ${visit.visit_time} · ${visit.department}` : "No visit scheduled"}
                      </td>
                      <td className="px-5 py-4">
                        {visit ? (
                          <Link href={`/visits/${visit.visit_id}`} className="btn-secondary">
                            Open Intake Workspace
                          </Link>
                        ) : (
                          <span className="text-slate">Schedule a visit above</span>
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
