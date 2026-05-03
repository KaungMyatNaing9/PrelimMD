import Link from "next/link";

export default function CompletePage() {
  return (
    <div className="page">
      <div className="panel success-panel">
        <span className="success-icon">✅</span>
        <h1>Check-In Complete!</h1>
        <p style={{ marginTop: "0.75rem", marginBottom: "2rem" }}>
          Your information has been received. Please take a seat — a staff member will call you
          shortly.
        </p>
        <div style={{ display: "grid", gap: "0.75rem", maxWidth: "28rem", margin: "0 auto", textAlign: "left" }}>
          {[
            "Your forms are now with your care team.",
            "Bring your insurance card if you have it.",
            "Let the front desk know if anything has changed.",
          ].map((tip) => (
            <div key={tip} style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start", fontSize: "0.95rem", color: "var(--text-soft)" }}>
              <span>•</span>
              <span>{tip}</span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: "2.5rem" }}>
          <Link href="/" className="btn btn-secondary">
            Return to Start
          </Link>
        </div>
      </div>
    </div>
  );
}
