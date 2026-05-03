"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { createNewPatientCheckin } from "@/lib/api";

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function nextTimeSlot() {
  const now = new Date();
  now.setMinutes(Math.ceil(now.getMinutes() / 15) * 15, 0, 0);
  return now.toTimeString().slice(0, 5);
}

export default function NewPatientPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    date_of_birth: "",
    gender: "",
    phone: "",
    email: "",
    address: "",
    appointment_date: todayIsoDate(),
    appointment_time: nextTimeSlot(),
    reason_for_visit: "",
    department: "General Medicine",
    provider_name: "Care Team",
  });

  const requiredReady = useMemo(
    () =>
      Boolean(
        form.first_name &&
          form.last_name &&
          form.date_of_birth &&
          form.gender &&
          form.phone &&
          form.appointment_date &&
          form.appointment_time &&
          form.reason_for_visit
      ),
    [form]
  );

  const set = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!requiredReady) {
      setError("Please fill in all required fields before continuing.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const created = await createNewPatientCheckin(form);
      router.push(`/checkin/${created.visit.visit_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "We couldn't create your new patient profile.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <Link href="/verify" className="section-label" style={{ textDecoration: "none" }}>
        Back to returning patient check-in
      </Link>

      <div className="panel">
        <h2>First-Time Patient Check-In</h2>
        <p style={{ marginBottom: "1.5rem" }}>
          We&apos;ll create your visit profile first, then guide you through the remaining forms on
          the kiosk.
        </p>

        <form onSubmit={handleSubmit} className="form-grid">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="field">
              <label htmlFor="first_name">First Name</label>
              <input id="first_name" className="input" value={form.first_name} onChange={set("first_name")} />
            </div>
            <div className="field">
              <label htmlFor="last_name">Last Name</label>
              <input id="last_name" className="input" value={form.last_name} onChange={set("last_name")} />
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="field">
              <label htmlFor="date_of_birth">Date of Birth</label>
              <input id="date_of_birth" type="date" className="input" value={form.date_of_birth} onChange={set("date_of_birth")} />
            </div>
            <div className="field">
              <label htmlFor="gender">Gender</label>
              <select id="gender" className="input" value={form.gender} onChange={set("gender")}>
                <option value="">Select</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="non-binary">Non-binary</option>
                <option value="prefer_not_to_say">Prefer not to say</option>
              </select>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="field">
              <label htmlFor="phone">Phone Number</label>
              <input id="phone" className="input" value={form.phone} onChange={set("phone")} />
            </div>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input id="email" type="email" className="input" value={form.email} onChange={set("email")} />
            </div>
          </div>

          <div className="field">
            <label htmlFor="address">Home Address</label>
            <input id="address" className="input" value={form.address} onChange={set("address")} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="field">
              <label htmlFor="appointment_date">Visit Date</label>
              <input id="appointment_date" type="date" className="input" value={form.appointment_date} onChange={set("appointment_date")} />
            </div>
            <div className="field">
              <label htmlFor="appointment_time">Visit Time</label>
              <input id="appointment_time" type="time" className="input" value={form.appointment_time} onChange={set("appointment_time")} />
            </div>
          </div>

          <div className="field">
            <label htmlFor="reason_for_visit">Reason For Visit</label>
            <input id="reason_for_visit" className="input" value={form.reason_for_visit} onChange={set("reason_for_visit")} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div className="field">
              <label htmlFor="department">Department</label>
              <input id="department" className="input" value={form.department} onChange={set("department")} />
            </div>
            <div className="field">
              <label htmlFor="provider_name">Provider</label>
              <input id="provider_name" className="input" value={form.provider_name} onChange={set("provider_name")} />
            </div>
          </div>

          {error ? <div className="error-msg">{error}</div> : null}

          <div className="btn-row">
            <button type="submit" className="btn btn-primary btn-full" disabled={busy}>
              {busy ? "Creating profile..." : "Create profile and continue"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
