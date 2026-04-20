"use client";

import { useEffect, useState } from "react";
import {
  bookAppointment,
  getBookingConfirmation,
  getReport,
  getSchedulingSlots,
  type AppointmentSlot,
  type BookingConfirmation,
  type IntakeReport,
} from "@/lib/api";

export default function SchedulingWidget() {
  const [report, setReport] = useState<IntakeReport | null>(null);
  const [slots, setSlots] = useState<AppointmentSlot[]>([]);
  const [booking, setBooking] = useState<BookingConfirmation | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [bookingSlotId, setBookingSlotId] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    void Promise.all([getReport(), getSchedulingSlots(), getBookingConfirmation()])
      .then(([nextReport, nextSlots, existingBooking]) => {
        if (!isMounted) {
          return;
        }

        setReport(nextReport);
        setSlots(nextSlots);
        setBooking(existingBooking);
      })
      .catch((error) => {
        if (isMounted) {
          setErrorMessage(
            error instanceof Error ? error.message : "Unable to load scheduling options."
          );
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  async function handleBook(slotId: string) {
    setBookingSlotId(slotId);
    setErrorMessage(null);

    try {
      const confirmation = await bookAppointment(slotId);
      setBooking(confirmation);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to book the selected appointment."
      );
    } finally {
      setBookingSlotId(null);
    }
  }

  return (
    <section className="schedule-shell">
      {report ? (
        <section className="panel spotlight-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Booking options</p>
              <h2>Matched to the intake report</h2>
            </div>
            <span className={`status-badge status-${report.riskLevel}`}>{report.riskLevel}</span>
          </div>
          <p className="supporting-text">
            The scheduling screen can react to the report risk level and recommended routing,
            which makes the end-to-end demo feel connected even before the real integration is
            finished.
          </p>
          <div className="field-list">
            <article className="field-card">
              <p className="label">Chief complaint</p>
              <p>{report.chiefComplaint}</p>
            </article>
            <article className="field-card">
              <p className="label">Routing hint</p>
              <p>{report.recommendedRouting}</p>
            </article>
          </div>
        </section>
      ) : null}

      {booking ? (
        <section className="panel confirmation-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Booking confirmed</p>
              <h2>{booking.slot.doctor}</h2>
            </div>
            <span className="status-badge status-done">Confirmed</span>
          </div>
          <p className="supporting-text">{booking.message}</p>
          <div className="field-list">
            <article className="field-card">
              <p className="label">Appointment time</p>
              <p>
                {booking.slot.dateLabel} at {booking.slot.timeLabel}
              </p>
            </article>
            <article className="field-card">
              <p className="label">Location</p>
              <p>
                {booking.slot.location} · {booking.slot.visitType}
              </p>
            </article>
          </div>
          <ul className="clean-list">
            {booking.instructions.map((instruction) => (
              <li key={instruction}>{instruction}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Available visits</p>
            <h2>Choose the best next step</h2>
          </div>
        </div>
        {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
        <div className="slot-grid">
          {slots.map((slot) => (
            <article key={slot.id} className="slot-card">
              <div className="slot-topline">
                <span className="status-badge status-idle">{slot.specialty}</span>
                <p className="label">{slot.visitType}</p>
              </div>
              <h3>{slot.doctor}</h3>
              <p className="supporting-text">{slot.recommendation}</p>
              <div className="slot-metadata">
                <p>
                  <strong>{slot.dateLabel}</strong> · {slot.timeLabel}
                </p>
                <p>{slot.location}</p>
              </div>
              <button
                type="button"
                className="button full"
                onClick={() => handleBook(slot.id)}
                disabled={bookingSlotId === slot.id}
              >
                {bookingSlotId === slot.id ? "Booking..." : "Book this visit"}
              </button>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
