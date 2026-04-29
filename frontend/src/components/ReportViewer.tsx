"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  downloadReportPdf,
  getInterviewSession,
  getLiveSessionId,
  isMockApiEnabled,
  getReport,
  type IntakeReport,
} from "@/lib/api";

export default function ReportViewer() {
  const [report, setReport] = useState<IntakeReport | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    let isMounted = true;

    // In live mode, always pull sessionId from the stored live session
    const sessionId = isMockApiEnabled ? undefined : (getLiveSessionId() ?? undefined);

    void getReport(sessionId)
      .then((nextReport) => {
        if (isMounted) setReport(nextReport);
      })
      .catch((error) => {
        if (isMounted) {
          setErrorMessage(
            error instanceof Error ? error.message : "Unable to load the patient report."
          );
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  async function handleDownloadPdf() {
    if (!report || isDownloading) return;
    setIsDownloading(true);
    try {
      await downloadReportPdf(report);
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? `PDF download failed: ${err.message}` : "PDF download failed."
      );
    } finally {
      setIsDownloading(false);
    }
  }

  if (errorMessage) {
    return <section className="panel"><p className="error-text">{errorMessage}</p></section>;
  }

  if (!report) {
    return <section className="panel"><p>Preparing your report…</p></section>;
  }

  return (
    <section className="report-shell">
      <div className="report-grid">
        <section className="panel spotlight-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Clinician-facing report</p>
              <h2>{report.chiefComplaint}</h2>
            </div>
            <span className={`status-badge status-${report.riskLevel}`}>{report.riskLevel}</span>
          </div>
          <p className="supporting-text">{report.summary}</p>
          <div className="field-list">
            <article className="field-card">
              <p className="label">Recommended routing</p>
              <p>{report.recommendedRouting}</p>
            </article>
            <article className="field-card">
              <p className="label">Clinical notes</p>
              <p>{report.notes}</p>
            </article>
          </div>
          <div className="button-row">
            <button
              type="button"
              className="button"
              onClick={handleDownloadPdf}
              disabled={isDownloading}
            >
              {isDownloading ? "Downloading…" : "Download PDF"}
            </button>
            <Link href="/booking" className="button secondary">
              Continue to booking
            </Link>
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Structured fields</p>
              <h2>Report-ready data</h2>
            </div>
          </div>
          <div className="field-list">
            {report.extractedFields.length > 0 ? (
              report.extractedFields.map((field) => (
                <article key={field.label} className="field-card">
                  <p className="label">{field.label}</p>
                  <p>{field.value}</p>
                </article>
              ))
            ) : (
              <p className="supporting-text">No structured fields extracted yet.</p>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Information gaps</p>
              <h2>Missing details</h2>
            </div>
          </div>
          {report.missingInformation.length > 0 ? (
            <ul className="clean-list">
              {report.missingInformation.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="supporting-text">All key fields captured — nothing missing.</p>
          )}
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Recommended next steps</p>
              <h2>What happens after intake</h2>
            </div>
          </div>
          <ul className="clean-list">
            {report.nextSteps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </section>
      </div>

      <section className="panel transcript-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Conversation record</p>
            <h2>Interview transcript</h2>
          </div>
        </div>
        <div className="message-list compact-list">
          {report.transcript.map((turn) => (
            <article
              key={turn.id}
              className={`message-row ${turn.role === "ai" ? "message-ai" : "message-user"}`}
            >
              <div className="message-bubble">
                <div className="message-meta">
                  <span>{turn.role === "ai" ? "Maya" : "You"}</span>
                  <span>{new Date(turn.timestamp).toLocaleString()}</span>
                </div>
                <p>{turn.content}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
