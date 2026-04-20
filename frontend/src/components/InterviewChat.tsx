"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState, useTransition } from "react";
import {
  completeInterview,
  getInterviewSession,
  isMockApiEnabled,
  resetInterview,
  sendInterviewAnswer,
  startInterview,
  type InterviewSessionState,
  type TranscriptSource,
} from "@/lib/api";
import VoiceInput from "@/components/VoiceInput";

function formatClock(timestamp: string) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

export default function InterviewChat() {
  const [session, setSession] = useState<InterviewSessionState | null>(null);
  const [draft, setDraft] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [submissionSource, setSubmissionSource] = useState<TranscriptSource>("typed");
  const [isWorking, setIsWorking] = useState(false);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    setSession(getInterviewSession());
  }, []);

  async function handleSessionAction(
    action: () => Promise<InterviewSessionState>,
    nextDraft = "",
    nextSource: TranscriptSource = "typed"
  ) {
    setIsWorking(true);
    setErrorMessage(null);

    try {
      const nextSession = await action();
      startTransition(() => {
        setSession(nextSession);
        setDraft(nextDraft);
        setSubmissionSource(nextSource);
      });
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Something went wrong while updating the session."
      );
    } finally {
      setIsWorking(false);
    }
  }

  async function beginSession() {
    await handleSessionAction(() => startInterview());
  }

  async function submitAnswer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!session || !draft.trim()) {
      return;
    }

    const answerToSend = draft.trim();
    const source = submissionSource;

    await handleSessionAction(
      () => sendInterviewAnswer(session.sessionId, answerToSend, source),
      "",
      "typed"
    );
  }

  async function endSessionNow() {
    if (!session) {
      return;
    }

    await handleSessionAction(() => completeInterview(session.sessionId));
  }

  async function resetDemo() {
    setIsWorking(true);
    setErrorMessage(null);

    try {
      await resetInterview();
      startTransition(() => {
        setSession(null);
        setDraft("");
        setSubmissionSource("typed");
      });
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to reset the current demo session."
      );
    } finally {
      setIsWorking(false);
    }
  }

  const busy = isWorking || isPending;

  if (!session) {
    return (
      <section className="panel empty-state">
        <span className="eyebrow">Session start</span>
        <h2>Begin the guided intake demo</h2>
        <p className="supporting-text">
          The interview flow below is wired for mock data first, which lets you demo the full
          frontend before the backend contract is finalized.
        </p>
        <div className="button-row">
          <button type="button" className="button" onClick={beginSession} disabled={busy}>
            Start intake session
          </button>
          <Link href="/report" className="button ghost">
            View sample report
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="chat-shell">
      <div className="split-layout">
        <div className="panel chat-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Interview workspace</p>
              <h2>Live patient intake</h2>
            </div>
            <div className="badge-row">
              <span
                className={`status-badge ${
                  session.status === "completed" ? "status-done" : "status-live"
                }`}
              >
                {session.status === "completed" ? "Complete" : "In progress"}
              </span>
              <span className="status-badge status-idle">
                {isMockApiEnabled ? "Mock API" : "Live API"}
              </span>
            </div>
          </div>
          <div className="progress-card">
            <div className="progress-header">
              <span>Session progress</span>
              <strong>{Math.round(session.progress)}%</strong>
            </div>
            <div className="progress-track" aria-hidden="true">
              <div className="progress-fill" style={{ width: `${session.progress}%` }} />
            </div>
            <p className="muted-text">{session.routingHint}</p>
          </div>
          <div className="message-list">
            {session.transcript.map((turn) => (
              <article
                key={turn.id}
                className={`message-row ${turn.role === "ai" ? "message-ai" : "message-user"}`}
              >
                <div className="message-bubble">
                  <div className="message-meta">
                    <span>{turn.role === "ai" ? "PrelimMD" : "Patient"}</span>
                    <span>{formatClock(turn.timestamp)}</span>
                  </div>
                  <p>{turn.content}</p>
                </div>
              </article>
            ))}
          </div>
          {session.status === "completed" ? (
            <div className="completion-card">
              <p className="eyebrow">Session complete</p>
              <h3>Ready for report review and booking</h3>
              <p className="supporting-text">
                The interview summary is saved locally so you can move into the next frontend
                screens immediately.
              </p>
              <div className="button-row">
                <Link href="/report" className="button">
                  Open report
                </Link>
                <Link href="/booking" className="button secondary">
                  See booking options
                </Link>
                <button type="button" className="button ghost" onClick={resetDemo} disabled={busy}>
                  Start over
                </button>
              </div>
            </div>
          ) : (
            <form className="composer" onSubmit={submitAnswer}>
              <label className="label" htmlFor="patient-answer">
                Current patient response
              </label>
              <textarea
                id="patient-answer"
                className="text-field"
                value={draft}
                rows={4}
                placeholder={session.currentQuestion ?? "Type the patient's answer here"}
                onChange={(event) => {
                  setDraft(event.target.value);
                  setSubmissionSource("typed");
                }}
              />
              <div className="button-row">
                <button type="submit" className="button" disabled={busy || !draft.trim()}>
                  Send answer
                </button>
                <button
                  type="button"
                  className="button secondary"
                  onClick={endSessionNow}
                  disabled={busy}
                >
                  End and review report
                </button>
                <button type="button" className="button ghost" onClick={resetDemo} disabled={busy}>
                  Reset session
                </button>
              </div>
            </form>
          )}
          {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
        </div>

        <div className="side-column">
          <VoiceInput
            disabled={busy || session.status === "completed"}
            onTranscriptCaptured={(transcript) => {
              setDraft(transcript);
              setSubmissionSource("voice");
            }}
          />
          <section className="panel detail-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Extracted fields</p>
                <h2>Structured handoff data</h2>
              </div>
            </div>
            {session.extractedFields.length > 0 ? (
              <div className="field-list">
                {session.extractedFields.map((field) => (
                  <article key={field.label} className="field-card">
                    <p className="label">{field.label}</p>
                    <p>{field.value}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p className="supporting-text">
                Structured fields will populate as the patient answers the guided questions.
              </p>
            )}
          </section>
          <section className="panel detail-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Frontend note</p>
                <h2>What this screen proves</h2>
              </div>
            </div>
            <ul className="clean-list">
              <li>Start and end flow works.</li>
              <li>Transcript UI updates in real time.</li>
              <li>Voice placeholder hands text into the chat composer.</li>
              <li>Report and booking screens can consume structured session data next.</li>
            </ul>
          </section>
        </div>
      </div>
    </section>
  );
}
