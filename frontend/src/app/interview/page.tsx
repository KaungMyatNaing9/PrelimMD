import InterviewChat from "@/components/InterviewChat";

export default function InterviewPage() {
  return (
    <main className="page">
      <section className="hero">
        <span className="eyebrow">Interview flow</span>
        <h1>Capture the patient story with a guided, demo-ready chat experience.</h1>
        <p className="supporting-text">
          This screen is built to prove your frontend scope first: session controls, live
          transcript handoff, mock API integration, and structured data extraction.
        </p>
      </section>
      <InterviewChat />
    </main>
  );
}
