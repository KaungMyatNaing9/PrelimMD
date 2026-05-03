"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { validateIdentity } from "@/lib/api";

const STEPS = ["Verify", "Review", "Complete Fields", "Sign & Submit"];

function VerifyForm() {
  const router = useRouter();
  const params = useSearchParams();

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    date_of_birth: "",
    visit_date: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Pre-fill visit_id hint from staff portal link
  const hintVisitId = params.get("visit_id");

  useEffect(() => {
    // If the staff portal passed a visit_id, we could pre-fill visit_date
    // from a lookup, but for simplicity we just show the field.
    void hintVisitId;
  }, [hintVisitId]);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.first_name || !form.last_name || !form.date_of_birth || !form.visit_date) {
      setError("Please fill in all fields.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await validateIdentity(
        form.first_name,
        form.last_name,
        form.date_of_birth,
        form.visit_date
      );
      if (!result.valid || !result.visit) {
        setError(result.message);
        return;
      }
      router.push(`/checkin/${result.visit.visit_id}`);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not find your appointment. Please check your details or ask a staff member."
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      {/* Step indicator */}
      <div style={{ display: "flex", gap: "0" }} className="step-list">
        {STEPS.map((s, i) => (
          <div key={s} className="step-item">
            <div className={`step-dot ${i === 0 ? "active" : ""}`}>{i === 0 ? i + 1 : "✓"[0] && i + 1}</div>
            <div className={`step-label ${i === 0 ? "active" : ""}`}>{s}</div>
          </div>
        ))}
      </div>

      <div className="panel">
        <h2>Verify Your Identity</h2>
        <p style={{ marginBottom: "1.5rem" }}>
          Enter your details exactly as they appear on your appointment confirmation.
        </p>

        <form onSubmit={handleSubmit} className="form-grid">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
            <div className="field">
              <label htmlFor="first_name">First Name</label>
              <input
                id="first_name"
                className={`input${form.first_name ? " has-value" : ""}`}
                placeholder="Jane"
                value={form.first_name}
                onChange={set("first_name")}
                autoComplete="given-name"
              />
            </div>
            <div className="field">
              <label htmlFor="last_name">Last Name</label>
              <input
                id="last_name"
                className={`input${form.last_name ? " has-value" : ""}`}
                placeholder="Smith"
                value={form.last_name}
                onChange={set("last_name")}
                autoComplete="family-name"
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="dob">Date of Birth</label>
            <input
              id="dob"
              type="date"
              className={`input${form.date_of_birth ? " has-value" : ""}`}
              value={form.date_of_birth}
              onChange={set("date_of_birth")}
              autoComplete="bday"
            />
          </div>

          <div className="field">
            <label htmlFor="visit_date">Visit Date (Today&apos;s appointment)</label>
            <input
              id="visit_date"
              type="date"
              className={`input${form.visit_date ? " has-value" : ""}`}
              value={form.visit_date}
              onChange={set("visit_date")}
            />
            <div className="input-hint">Enter the date of your appointment today.</div>
          </div>

          {error && <div className="error-msg">{error}</div>}

          <button type="submit" className="btn btn-primary btn-full" disabled={busy}>
            {busy ? "Verifying…" : "Continue →"}
          </button>
        </form>

        <div style={{ marginTop: "1.4rem", paddingTop: "1.2rem", borderTop: "1px solid rgba(20, 39, 59, 0.1)" }}>
          <div className="section-label">First time here?</div>
          <p style={{ marginBottom: "1rem" }}>
            New patients can create a check-in profile first, then complete the rest of their
            intake on the kiosk.
          </p>
          <button
            type="button"
            className="btn btn-secondary btn-full"
            onClick={() => router.push("/new-patient")}
          >
            I&apos;m a new patient
          </button>
        </div>
      </div>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense>
      <VerifyForm />
    </Suspense>
  );
}
