import ReportViewer from "@/components/ReportViewer";

export default function ReportPage() {
  return (
    <main className="page">
      <section className="hero">
        <span className="eyebrow">Report review</span>
        <h1>Turn the conversation into a clinician-facing summary.</h1>
        <p className="supporting-text">
          The report screen translates interview answers into the kind of structured handoff data
          the backend services will eventually generate for real.
        </p>
      </section>
      <ReportViewer />
    </main>
  );
}
