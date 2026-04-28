import Link from "next/link";
import PdfUploadDropzone from "@/components/PdfUploadDropzone";

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
            This frontend prototype covers the full patient-side experience: start the session,
            capture answers, review a clinician-facing report, and move into appointment booking.
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

      <section className="panel spotlight-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Clinician setup</p>
            <h2>Load a custom intake form</h2>
          </div>
        </div>
        <p className="supporting-text">
          Drop any clinical intake PDF below. The AI parses it into a structured question form and
          drives the patient interview automatically.
        </p>
        <PdfUploadDropzone />
      </section>

      <section className="card-grid">
        {featureCards.map((card) => (
          <article key={card.title} className="panel feature-card">
            <p className="eyebrow">Frontend deliverable</p>
            <h2>{card.title}</h2>
            <p className="supporting-text">{card.description}</p>
            <Link href={card.href} className="button ghost">
              Open screen
            </Link>
          </article>
        ))}
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">What this branch covers</p>
            <h2>Your frontend scope in simple terms</h2>
          </div>
        </div>
        <div className="field-list">
          <article className="field-card">
            <p className="label">Patient experience</p>
            <p>Landing page, session start, chat view, transcript preview, and clear actions.</p>
          </article>
          <article className="field-card">
            <p className="label">Data display</p>
            <p>Report summary, extracted fields, risk badges, and next-step guidance.</p>
          </article>
          <article className="field-card">
            <p className="label">Scheduling handoff</p>
            <p>Doctor options, available visit types, and appointment confirmation UI.</p>
          </article>
        </div>
      </section>
    </main>
  );
}
