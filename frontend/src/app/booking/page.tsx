import SchedulingWidget from "@/components/SchedulingWidget";

export default function BookingPage() {
  return (
    <main className="page">
      <section className="hero">
        <span className="eyebrow">Scheduling handoff</span>
        <h1>Show patients the next best appointment without breaking the flow.</h1>
        <p className="supporting-text">
          This booking view consumes the report output and turns it into visit options, which is
          exactly the handoff your final integrated demo needs.
        </p>
      </section>
      <SchedulingWidget />
    </main>
  );
}
