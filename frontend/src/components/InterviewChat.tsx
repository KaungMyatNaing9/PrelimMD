"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState, useTransition } from "react";
import {
  completeInterview,
  getInterviewSession,
  isMockApiEnabled,
  resetInterview,
  sendInterviewAnswer,
  startInterview,
  synthesizeSpeech,
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

  // Maya voice state
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [mayaSpeaking, setMayaSpeaking] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  useEffect(() => {
    setSession(getInterviewSession());
  }, []);

  const stopCurrentAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    setMayaSpeaking(false);
  }, []);

  const speakMayaMessage = useCallback(
    async (text: string) => {
      if (!voiceEnabled || !text.trim()) return;
      stopCurrentAudio();

      try {
        setMayaSpeaking(true);
        const blob = await synthesizeSpeech(text);
        const url = URL.createObjectURL(blob);
        audioUrlRef.current = url;

        const audio = new Audio(url);
        audioRef.current = audio;

        audio.onended = () => {
          setMayaSpeaking(false);
          URL.revokeObjectURL(url);
          audioUrlRef.current = null;
          audioRef.current = null;
        };
        audio.onerror = () => {
          setMayaSpeaking(false);
        };

        await audio.play();
      } catch {
        setMayaSpeaking(false);
      }
    },
    [voiceEnabled, stopCurrentAudio]
  );

  // Cleanup audio on unmount
  useEffect(() => {
    return () => stopCurrentAudio();
  }, [stopCurrentAudio]);

  async function handleSessionAction(
    action: () => Promise<InterviewSessionState>,
    nextDraft = "",
    nextSource: TranscriptSource = "typed"
  ) {
    stopCurrentAudio();
    setIsWorking(true);
    setErrorMessage(null);

    try {
      const nextSession = await action();
      startTransition(() => {
        setSession(nextSession);
        setDraft(nextDraft);
        setSubmissionSource(nextSource);
      });

      // Speak Maya's latest message after state updates
      if (nextSession.currentQuestion) {
        void speakMayaMessage(nextSession.currentQuestion);
      } else if (nextSession.status === "completed") {
        // Speak the last AI turn (the closing message)
        const lastAiTurn = [...nextSession.transcript].reverse().find((t) => t.role === "ai");
        if (lastAiTurn) void speakMayaMessage(lastAiTurn.content);
      }
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
    if (!session || !draft.trim()) return;
    const answerToSend = draft.trim();
    const source = submissionSource;
    await handleSessionAction(
      () => sendInterviewAnswer(session.sessionId, answerToSend, source),
      "",
      "typed"
    );
  }

  async function endSessionNow() {
    if (!session) return;
    await handleSessionAction(() => completeInterview(session.sessionId));
  }

  async function resetDemo() {
    stopCurrentAudio();
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
        error instanceof Error ? error.message : "Unable to reset the current session."
      );
    } finally {
      setIsWorking(false);
    }
  }

  const busy = isWorking || isPending;

  if (!session) {
    return (
      <section className="panel empty-state">
        <span className="eyebrow">Pre-visit intake</span>
        <h2>Ready when you are</h2>
        <p className="supporting-text">
          Maya, your pre-visit nurse, will walk you through a brief intake conversation — about
          5 minutes — so your doctor has everything they need before your appointment.
        </p>
        <div className="button-row">
          <button type="button" className="button" onClick={beginSession} disabled={busy}>
            Start intake
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
              <p className="eyebrow">Pre-visit intake</p>
              <h2>Maya — Your Intake Nurse</h2>
            </div>
            <div className="badge-row">
              <span
                className={`status-badge ${
                  session.status === "completed" ? "status-done" : "status-live"
                }`}
              >
                {session.status === "completed" ? "Complete" : "In progress"}
              </span>
              {mayaSpeaking ? (
                <span className="status-badge status-live">Maya speaking…</span>
              ) : (
                <button
                  type="button"
                  className="status-badge status-idle"
                  style={{ cursor: "pointer", border: "none", background: "none" }}
                  onClick={() => {
                    stopCurrentAudio();
                    setVoiceEnabled((v) => !v);
                  }}
                  title={voiceEnabled ? "Mute Maya's voice" : "Unmute Maya's voice"}
                >
                  {voiceEnabled ? "🔊 Voice on" : "🔇 Voice off"}
                </button>
              )}
            </div>
          </div>
          <div className="progress-card">
            <div className="progress-header">
              <span>Intake progress</span>
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
                    <span>{turn.role === "ai" ? "Maya" : "You"}</span>
                    <span>{formatClock(turn.timestamp)}</span>
                  </div>
                  <p>{turn.content}</p>
                </div>
              </article>
            ))}
            {mayaSpeaking && (
              <article className="message-row message-ai">
                <div className="message-bubble">
                  <div className="message-meta">
                    <span>Maya</span>
                    <span>now</span>
                  </div>
                  <p style={{ opacity: 0.6, fontStyle: "italic" }}>Speaking…</p>
                </div>
              </article>
            )}
          </div>
          {session.status === "completed" ? (
            <div className="completion-card">
              <p className="eyebrow">Intake complete</p>
              <h3>Your doctor is all set</h3>
              <p className="supporting-text">
                Maya has prepared a summary for your physician. You can review it or jump straight
                to booking your appointment.
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
                Your response
              </label>
              <textarea
                id="patient-answer"
                className="text-field"
                value={draft}
                rows={4}
                placeholder={session.currentQuestion ?? "Type your response here…"}
                onChange={(event) => {
                  stopCurrentAudio();
                  setDraft(event.target.value);
                  setSubmissionSource("typed");
                }}
              />
              <div className="button-row">
                <button type="submit" className="button" disabled={busy || !draft.trim() || mayaSpeaking}>
                  Send
                </button>
                <button
                  type="button"
                  className="button secondary"
                  onClick={endSessionNow}
                  disabled={busy}
                >
                  Finish interview
                </button>
                <button type="button" className="button ghost" onClick={resetDemo} disabled={busy}>
                  Reset
                </button>
              </div>
            </form>
          )}
          {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
        </div>

        <div className="side-column">
          <VoiceInput
            sessionId={session.sessionId}
            disabled={busy || session.status === "completed" || mayaSpeaking}
            onTranscriptCaptured={(transcript) => {
              stopCurrentAudio();
              if (!transcript.trim() || session.status === "completed" || busy) {
                setDraft(transcript);
                setSubmissionSource("voice");
                return;
              }
              // Auto-submit the voice answer directly — no need to press Send
              void handleSessionAction(
                () => sendInterviewAnswer(session.sessionId, transcript.trim(), "voice"),
                "",
                "typed"
              );
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
                Structured fields will appear here as Maya gathers your information.
              </p>
            )}
          </section>
          <section className="panel detail-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">How it works</p>
                <h2>Your intake, your way</h2>
              </div>
            </div>
            <ul className="clean-list">
              <li>Type your answers or use the mic — your choice.</li>
              <li>Maya asks one question at a time and adapts to what you share.</li>
              <li>Your doctor receives a clear summary before you arrive.</li>
              <li>Nothing is shared without your knowledge.</li>
            </ul>
          </section>
        </div>
      </div>
    </section>
  );
}
