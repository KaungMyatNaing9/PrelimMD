import Link from "next/link";

export default function WelcomePage() {
  return (
    <div className="page">
      <div className="panel welcome-hero">
        <span className="welcome-icon">🏥</span>
        <h1>Welcome to PrelimMD</h1>
        <p>
          Complete your check-in quickly and securely. We&apos;ll verify your identity, review your
          intake form, and collect your consent — all in a few steps.
        </p>
        <Link href="/verify" className="btn btn-primary" style={{ display: "inline-flex" }}>
          Start Check-In →
        </Link>
      </div>

      <div className="panel" style={{ padding: "1.5rem 2rem" }}>
        <div className="section-label">What to expect</div>
        <div style={{ display: "grid", gap: "1rem" }}>
          {[
            { step: "1", title: "Verify your identity", desc: "Enter your name, date of birth, and visit date." },
            { step: "2", title: "Review your form", desc: "We've pre-filled what we know. Confirm or correct any details." },
            { step: "3", title: "Complete missing fields", desc: "Answer any remaining questions we need for your visit." },
            { step: "4", title: "Sign & submit", desc: "Provide your electronic consent and you're done." },
          ].map((item) => (
            <div key={item.step} style={{ display: "flex", gap: "1rem", alignItems: "flex-start" }}>
              <div style={{
                width: "2rem", height: "2rem", borderRadius: "999px",
                background: "rgba(21,94,99,0.1)", color: "var(--accent-strong)",
                display: "grid", placeItems: "center", fontWeight: 700, flexShrink: 0, fontSize: "0.9rem"
              }}>
                {item.step}
              </div>
              <div>
                <div style={{ fontWeight: 600, marginBottom: "0.2rem" }}>{item.title}</div>
                <div style={{ fontSize: "0.9rem", color: "var(--text-soft)", lineHeight: 1.5 }}>{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
