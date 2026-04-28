import Link from "next/link";

const featureCards = [
  {
    title: "Live interview UI",
    description:
      "A patient-friendly intake flow with chat bubbles, session controls, and transcript capture.",
    href: "/interview",
  },
  {
    title: "Structured report screen",
    description:
      "A clinician-facing summary that turns the conversation into reviewable fields and next steps.",
    href: "/report",
  },
  {
    title: "Booking options",
    description:
      "A scheduling screen that reacts to report severity and offers realistic appointment slots.",
    href: "/booking",
  },
];

export default function HomePage() {
  return (
    <main className="page">
      <section className="hero hero-grid">
        <div className="hero-copy">
          <span className="eyebrow">Voice-first patient engagement</span>
          <h1>PrelimMD turns a stressful intake into a guided, calm first step.</h1>
          <p className="supporting-text">
            Start the intake conversation, capture patient responses in real time, review the
            clinical summary, and move directly into the next care option.
          </p>
          <div className="button-row">
            <Link href="/interview" className="button">
              Launch interview demo
            </Link>
            <Link href="/report" className="button secondary">
              View report screen
            </Link>
          </div>
        </div>
        <div className="hero-panel">
          <p className="eyebrow">Prototype flow</p>
          <div className="metric-stack">
            <article className="metric-card">
              <strong>01</strong>
              <p>Patient starts a guided intake instead of filling a long form.</p>
            </article>
            <article className="metric-card">
              <strong>02</strong>
              <p>Conversation and voice notes are turned into structured summary fields.</p>
            </article>
            <article className="metric-card">
              <strong>03</strong>
              <p>Report and scheduling views carry the patient into the next action smoothly.</p>
            </article>
          </div>
        </div>
      </section>

      <section className="card-grid">
        {featureCards.map((card) => (
          <article key={card.title} className="panel feature-card">
            <p className="eyebrow">Experience</p>
            <h2>{card.title}</h2>
            <p className="supporting-text">{card.description}</p>
            <Link href={card.href} className="button ghost">
              Open screen
            </Link>
          </article>
        ))}
      </section>
    </main>
  );
}
