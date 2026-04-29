"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type VoiceInputProps = {
  disabled?: boolean;
  sessionId?: string;
  onTranscriptCaptured: (transcript: string) => void;
};

type VoiceStreamMessage =
  | { type: "connected" }
  | { type: "transcribing" }
  | { type: "partial"; transcript: string; confidence?: number }
  | { type: "final"; transcript: string; confidence?: number; llm_response?: string }
  | { type: "error"; message: string };

function buildVoiceSocketUrl(sessionId?: string) {
  const explicitUrl = process.env.NEXT_PUBLIC_VOICE_WS_URL?.trim();
  let base: string;

  if (explicitUrl) {
    base = explicitUrl;
  } else {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
    if (!apiUrl) {
      base = "ws://localhost:8000/voice/stream";
    } else {
      const normalized = apiUrl
        .replace(/^http:\/\//i, "ws://")
        .replace(/^https:\/\//i, "wss://");
      base = `${normalized.replace(/\/$/, "")}/voice/stream`;
    }
  }

  return sessionId ? `${base}?session_id=${encodeURIComponent(sessionId)}` : base;
}

function getRecorderMimeType() {
  if (typeof window === "undefined" || typeof MediaRecorder === "undefined") return undefined;
  const preferred = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return preferred.find((t) => MediaRecorder.isTypeSupported(t));
}

export default function VoiceInput({ disabled = false, sessionId, onTranscriptCaptured }: VoiceInputProps) {
  const socketUrl = useMemo(() => buildVoiceSocketUrl(sessionId), [sessionId]);
  const meterBars = useMemo(() => Array.from({ length: 18 }, (_, i) => i), []);

  const websocketRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const finalTranscriptRef = useRef("");

  const [isSupported, setIsSupported] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [latestFinalTranscript, setLatestFinalTranscript] = useState("");
  const [statusMessage, setStatusMessage] = useState(
    "Click the mic to start recording. Your speech will be transcribed when you stop."
  );

  useEffect(() => {
    const supported =
      typeof window !== "undefined" &&
      typeof window.WebSocket !== "undefined" &&
      typeof window.MediaRecorder !== "undefined" &&
      typeof navigator !== "undefined" &&
      !!navigator.mediaDevices?.getUserMedia;

    setIsSupported(supported);
    if (!supported) {
      setStatusMessage("Voice not supported in this browser. Use Chrome or Edge.");
    }
    return () => cleanupResources();
  }, []);

  function stopRecorder() {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
    recorderRef.current = null;
  }

  function stopMediaStream() {
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
  }

  function cleanupResources() {
    stopRecorder();
    stopMediaStream();
    const ws = websocketRef.current;
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      ws.close();
    }
    websocketRef.current = null;
  }

  function clearTranscript() {
    cleanupResources();
    finalTranscriptRef.current = "";
    setLiveTranscript("");
    setLatestFinalTranscript("");
    setIsRecording(false);
    setIsConnecting(false);
    setIsTranscribing(false);
    setStatusMessage(
      isSupported
        ? "Cleared. Click the mic when you're ready."
        : "Voice not supported — type your answer instead."
    );
  }

  function stopRecording() {
    // Stop the microphone — but DON'T close the WebSocket yet.
    // Send a {"type":"stop"} signal so the backend knows to transcribe.
    stopRecorder();
    stopMediaStream();
    setIsRecording(false);
    setIsTranscribing(true);
    setStatusMessage("Transcribing your speech…");

    const ws = websocketRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "stop" }));
      // WebSocket stays open — backend will send the final transcript back
    } else {
      setIsTranscribing(false);
      setStatusMessage("Connection lost before transcription. Please try again.");
    }
  }

  async function startRecording() {
    if (disabled || !isSupported || isRecording || isConnecting || isTranscribing) return;

    setIsConnecting(true);
    setStatusMessage("Connecting to voice service…");
    setLiveTranscript("");
    setLatestFinalTranscript("");
    finalTranscriptRef.current = "";

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = mediaStream;

      const mimeType = getRecorderMimeType();
      const recorder = mimeType
        ? new MediaRecorder(mediaStream, { mimeType })
        : new MediaRecorder(mediaStream);
      recorderRef.current = recorder;

      const ws = new WebSocket(socketUrl);
      websocketRef.current = ws;

      ws.onmessage = (event) => {
        let msg: VoiceStreamMessage;
        try {
          msg = JSON.parse(event.data as string) as VoiceStreamMessage;
        } catch {
          return;
        }

        if (msg.type === "connected") {
          setStatusMessage("Connected — speak clearly. Click Stop when done.");
          return;
        }

        if (msg.type === "transcribing") {
          setIsTranscribing(true);
          setStatusMessage("Transcribing your speech…");
          return;
        }

        if (msg.type === "partial") {
          if (msg.transcript && msg.transcript !== "Listening…") {
            setLiveTranscript(msg.transcript);
          }
          return;
        }

        if (msg.type === "error") {
          setIsTranscribing(false);
          setIsRecording(false);
          setStatusMessage(`${msg.message}`);
          // Close WebSocket on error
          if (ws.readyState === WebSocket.OPEN) ws.close();
          websocketRef.current = null;
          return;
        }

        if (msg.type === "final") {
          setIsTranscribing(false);
          setIsConnecting(false);
          finalTranscriptRef.current = msg.transcript;
          setLiveTranscript("");
          setLatestFinalTranscript(msg.transcript);
          setStatusMessage("Got it — submitting your answer…");
          onTranscriptCaptured(msg.transcript);
          // Now safe to close
          if (ws.readyState === WebSocket.OPEN) ws.close();
          websocketRef.current = null;
        }
      };

      ws.onerror = () => {
        cleanupResources();
        setIsTranscribing(false);
        setIsRecording(false);
        setIsConnecting(false);
        setStatusMessage("Could not connect to voice service. Check that the backend is running.");
      };

      ws.onclose = () => {
        stopRecorder();
        stopMediaStream();
        setIsTranscribing(false);
        setIsRecording(false);
        setIsConnecting(false);
      };

      // Wait for open
      await new Promise<void>((resolve, reject) => {
        ws.addEventListener("open", () => resolve(), { once: true });
        ws.addEventListener("error", () => reject(new Error("WebSocket failed to open")), { once: true });
      });

      recorder.ondataavailable = async (e) => {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          const buf = await e.data.arrayBuffer();
          ws.send(buf);
        }
      };

      recorder.start(250);
      setIsConnecting(false);
      setIsRecording(true);
      setStatusMessage("Recording — speak clearly. Click Stop when you're done.");
    } catch (err) {
      cleanupResources();
      setIsRecording(false);
      setIsConnecting(false);
      setIsTranscribing(false);
      setStatusMessage(
        err instanceof Error ? `Could not start mic: ${err.message}` : "Could not start microphone."
      );
    }
  }

  function toggleRecording() {
    if (!isSupported) {
      setStatusMessage("Voice not supported — use Chrome or Edge.");
      return;
    }
    if (isTranscribing) return; // Can't interrupt transcription
    if (isRecording || isConnecting) {
      stopRecording();
      return;
    }
    void startRecording();
  }

  const voiceVisualState = isTranscribing
    ? "connecting"
    : isConnecting
      ? "connecting"
      : isRecording
        ? "recording"
        : latestFinalTranscript
          ? "captured"
          : "idle";

  const orbLabel = isTranscribing
    ? "Wait"
    : isConnecting
      ? "Sync"
      : isRecording
        ? "Stop"
        : "Mic";

  const orbSubLabel = isTranscribing
    ? "Processing…"
    : isConnecting
      ? "Connecting"
      : isRecording
        ? "Recording"
        : "Start";

  const transcriptHeadline = liveTranscript
    ? "Listening live"
    : latestFinalTranscript
      ? "Transcript captured"
      : isTranscribing
        ? "Transcribing…"
        : "Awaiting microphone input";

  const transcriptPreview = liveTranscript || latestFinalTranscript;

  return (
    <section className="panel voice-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Voice input</p>
          <h2>Speak your answer</h2>
        </div>
        <span className={`status-badge ${isRecording || isConnecting || isTranscribing ? "status-live" : "status-idle"}`}>
          {isTranscribing ? "Transcribing" : isConnecting ? "Connecting" : isRecording ? "Recording" : isSupported ? "Ready" : "Unavailable"}
        </span>
      </div>

      <div className={`voice-stage voice-stage-simplified voice-stage-${voiceVisualState}`}>
        <div className={`voice-visual voice-visual-${voiceVisualState}`}>
          <div className="voice-beam voice-beam-left" />
          <div className="voice-beam voice-beam-right" />
          <div className="voice-aurora voice-aurora-one" />
          <div className="voice-aurora voice-aurora-two" />
          <div className="voice-ribbon voice-ribbon-a" />
          <div className="voice-ribbon voice-ribbon-b" />
          <div className="voice-ring voice-ring-one" />
          <div className="voice-ring voice-ring-two" />
          <div className="voice-halo voice-halo-outer" />
          <div className="voice-halo voice-halo-middle" />
          <div className="voice-halo voice-halo-inner" />
          <div className="voice-grid" aria-hidden="true" />
          <div className="voice-pulse-dot voice-pulse-dot-left" aria-hidden="true" />
          <div className="voice-pulse-dot voice-pulse-dot-right" aria-hidden="true" />
          <button
            type="button"
            className={`voice-orb ${isRecording ? "voice-orb-active" : ""}`}
            disabled={disabled || isTranscribing}
            onClick={toggleRecording}
          >
            <span className="voice-orb-glow" aria-hidden="true" />
            <span className="voice-orb-core">
              <span className="voice-orb-label">{orbLabel}</span>
              <strong>{orbSubLabel}</strong>
            </span>
          </button>
          <div className="voice-wave-shell" aria-hidden="true">
            <div className="voice-wave voice-wave-left">
              {meterBars.slice(0, 8).map((b) => (
                <span key={`l-${b}`} className="voice-wave-bar" style={{ animationDelay: `${b * 70}ms` }} />
              ))}
            </div>
            <div className="voice-wave voice-wave-right">
              {meterBars.slice(0, 8).map((b) => (
                <span key={`r-${b}`} className="voice-wave-bar" style={{ animationDelay: `${b * 70 + 120}ms` }} />
              ))}
            </div>
          </div>
          <div className="voice-eq voice-eq-bottom" aria-hidden="true">
            {meterBars.slice(0, 12).map((b) => (
              <span key={`eq-${b}`} className="voice-eq-bar" style={{ animationDelay: `${b * 80}ms` }} />
            ))}
          </div>
        </div>

        <div className="voice-copy">
          <p className="voice-kicker">{transcriptHeadline}</p>
          <h3 className="voice-headline">
            {isTranscribing
              ? "Transcribing your words…"
              : isRecording
                ? "The room is listening."
                : isConnecting
                  ? "Connecting to voice service."
                  : "Tap the mic to speak."}
          </h3>
          <p className="voice-status-line">{statusMessage}</p>
          <div className="voice-live-chip">
            <span className="voice-live-dot" />
            <span>{transcriptPreview || "Your speech will appear here."}</span>
          </div>
        </div>
      </div>

      <div className="voice-readout-grid voice-readout-grid-simplified">
        <div className="transcript-preview transcript-preview-live transcript-preview-hero">
          <p className="label">{liveTranscript ? "Live transcript" : "Captured response"}</p>
          <p>
            {transcriptPreview || "Speak into the mic — your words appear here, then auto-submit to Maya."}
          </p>
        </div>
      </div>

      <div className="button-row">
        {isRecording ? (
          <button type="button" className="button" onClick={stopRecording}>
            Stop recording
          </button>
        ) : null}
        {isTranscribing ? (
          <span className="status-badge status-live" style={{ padding: "8px 12px" }}>
            Transcribing…
          </span>
        ) : null}
        <button type="button" className="button secondary" onClick={clearTranscript} disabled={isTranscribing}>
          Clear
        </button>
      </div>
    </section>
  );
}
