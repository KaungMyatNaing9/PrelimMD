"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type VoiceInputProps = {
  disabled?: boolean;
  onTranscriptCaptured: (transcript: string) => void;
};

type VoiceStreamMessage =
  | {
      type: "partial";
      transcript: string;
      confidence?: number;
    }
  | {
      type: "final";
      transcript: string;
      confidence?: number;
      llm_response?: string;
    }
  | {
      type: "error";
      message: string;
    };

function buildVoiceSocketUrl() {
  const explicitUrl = process.env.NEXT_PUBLIC_VOICE_WS_URL?.trim();

  if (explicitUrl) {
    return explicitUrl;
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();

  if (!apiUrl) {
    return "ws://localhost:8000/voice/stream";
  }

  const normalizedApiUrl = apiUrl
    .replace(/^http:\/\//i, "ws://")
    .replace(/^https:\/\//i, "wss://");

  return `${normalizedApiUrl.replace(/\/$/, "")}/voice/stream`;
}

function getRecorderMimeType() {
  if (typeof window === "undefined" || typeof MediaRecorder === "undefined") {
    return undefined;
  }

  const preferredMimeTypes = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
  ];

  return preferredMimeTypes.find((mimeType) => MediaRecorder.isTypeSupported(mimeType));
}

export default function VoiceInput({
  disabled = false,
  onTranscriptCaptured,
}: VoiceInputProps) {
  const socketUrl = useMemo(buildVoiceSocketUrl, []);
  const meterBars = useMemo(() => Array.from({ length: 18 }, (_, index) => index), []);

  const websocketRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const finalTranscriptRef = useRef("");

  const [isSupported, setIsSupported] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [latestFinalTranscript, setLatestFinalTranscript] = useState("");
  const [llmResponse, setLlmResponse] = useState("");
  const [statusMessage, setStatusMessage] = useState(
    "Click the mic to stream audio to the backend live transcription service."
  );

  useEffect(() => {
    const browserSupportsRecording =
      typeof window !== "undefined" &&
      typeof window.WebSocket !== "undefined" &&
      typeof window.MediaRecorder !== "undefined" &&
      typeof navigator !== "undefined" &&
      !!navigator.mediaDevices?.getUserMedia;

    setIsSupported(browserSupportsRecording);

    if (!browserSupportsRecording) {
      setStatusMessage(
        "This browser cannot stream microphone audio. Use Chrome or Edge for the backend voice demo."
      );
    }

    return () => {
      cleanupResources();
    };
  }, []);

  function stopRecorder() {
    const currentRecorder = recorderRef.current;

    if (currentRecorder && currentRecorder.state !== "inactive") {
      currentRecorder.stop();
    }

    recorderRef.current = null;
  }

  function stopMediaStream() {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
  }

  function cleanupResources() {
    stopRecorder();
    stopMediaStream();

    if (websocketRef.current) {
      const currentSocket = websocketRef.current;

      if (
        currentSocket.readyState === WebSocket.OPEN ||
        currentSocket.readyState === WebSocket.CONNECTING
      ) {
        currentSocket.close();
      }
    }

    websocketRef.current = null;
  }

  function resetLocalVoiceState() {
    setIsRecording(false);
    setIsConnecting(false);
  }

  function clearTranscript() {
    cleanupResources();
    finalTranscriptRef.current = "";
    setLiveTranscript("");
    setLatestFinalTranscript("");
    setLlmResponse("");
    resetLocalVoiceState();
    setStatusMessage(
      isSupported
        ? "Transcript cleared. Click the mic when you want to start streaming again."
        : "This browser cannot stream microphone audio. Type into the response box instead."
    );
  }

  function stopRecording() {
    setStatusMessage("Stopping microphone stream...");

    stopRecorder();
    stopMediaStream();

    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.close();
    }

    setIsRecording(false);
    setIsConnecting(false);
  }

  async function startRecording() {
    if (disabled || !isSupported || isRecording || isConnecting) {
      return;
    }

    setIsConnecting(true);
    setStatusMessage("Preparing microphone stream...");
    setLiveTranscript("");
    setLatestFinalTranscript("");
    setLlmResponse("");
    finalTranscriptRef.current = "";

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = mediaStream;

      const recorderMimeType = getRecorderMimeType();
      const recorder = recorderMimeType
        ? new MediaRecorder(mediaStream, { mimeType: recorderMimeType })
        : new MediaRecorder(mediaStream);

      recorderRef.current = recorder;

      const websocket = new WebSocket(socketUrl);
      websocketRef.current = websocket;

      websocket.onmessage = (event) => {
        const message = JSON.parse(event.data) as VoiceStreamMessage;

        if (message.type === "error") {
          cleanupResources();
          resetLocalVoiceState();
          setStatusMessage(`Backend voice error: ${message.message}`);
          return;
        }

        if (message.type === "partial") {
          setLiveTranscript(message.transcript);
          setStatusMessage("Streaming audio to backend. Speak now...");
          return;
        }

        if (message.type === "final") {
          finalTranscriptRef.current = message.transcript;
          setLiveTranscript("");
          setLatestFinalTranscript(message.transcript);
          setLlmResponse(message.llm_response ?? "");
          setStatusMessage("Final transcript received from backend.");
          onTranscriptCaptured(message.transcript);
        }
      };

      websocket.onerror = () => {
        cleanupResources();
        setStatusMessage("Could not connect to the backend voice WebSocket.");
        resetLocalVoiceState();
      };

      websocket.onclose = () => {
        stopRecorder();
        stopMediaStream();
        resetLocalVoiceState();
      };

      await new Promise<void>((resolve, reject) => {
        websocket.addEventListener("open", () => resolve(), { once: true });
        websocket.addEventListener("error", () => reject(new Error("WebSocket failed")), {
          once: true,
        });
      });

      recorder.ondataavailable = async (event) => {
        if (
          event.data.size > 0 &&
          websocketRef.current &&
          websocketRef.current.readyState === WebSocket.OPEN
        ) {
          const buffer = await event.data.arrayBuffer();
          websocketRef.current.send(buffer);
        }
      };

      recorder.start(250);
      setIsConnecting(false);
      setIsRecording(true);
      setStatusMessage("Backend voice stream is live. Speak clearly into your microphone.");
    } catch (error) {
      cleanupResources();
      resetLocalVoiceState();
      setStatusMessage(
        error instanceof Error
          ? `Voice stream could not start: ${error.message}`
          : "Voice stream could not start."
      );
    }
  }

  function toggleRecording() {
    if (!isSupported) {
      setStatusMessage(
        "This browser cannot stream microphone audio. Use Chrome or Edge for the backend voice demo."
      );
      return;
    }

    if (isRecording || isConnecting) {
      stopRecording();
      return;
    }

    void startRecording();
  }

  const voiceVisualState = isConnecting
    ? "connecting"
    : isRecording
      ? "recording"
      : latestFinalTranscript
        ? "captured"
        : "idle";

  const transcriptHeadline = liveTranscript
    ? "Listening live"
    : latestFinalTranscript
      ? "Utterance captured"
      : "Awaiting microphone input";

  const transcriptPreview = liveTranscript || latestFinalTranscript;

  return (
    <section className="panel voice-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Voice capture</p>
          <h2>Mic and transcript preview</h2>
        </div>
        <span
          className={`status-badge ${
            isRecording || isConnecting ? "status-live" : "status-idle"
          }`}
        >
          {isConnecting ? "Connecting" : isRecording ? "Streaming" : isSupported ? "Ready" : "Unavailable"}
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
            disabled={disabled}
            onClick={toggleRecording}
          >
            <span className="voice-orb-glow" aria-hidden="true" />
            <span className="voice-orb-core">
              <span className="voice-orb-label">Mic</span>
              <strong>{isConnecting ? "Sync" : isRecording ? "Live" : "Start"}</strong>
            </span>
          </button>
          <div className="voice-wave-shell" aria-hidden="true">
            <div className="voice-wave voice-wave-left">
              {meterBars.slice(0, 8).map((bar) => (
                <span
                  key={`left-${bar}`}
                  className="voice-wave-bar"
                  style={{ animationDelay: `${bar * 70}ms` }}
                />
              ))}
            </div>
            <div className="voice-wave voice-wave-right">
              {meterBars.slice(0, 8).map((bar) => (
                <span
                  key={`right-${bar}`}
                  className="voice-wave-bar"
                  style={{ animationDelay: `${bar * 70 + 120}ms` }}
                />
              ))}
            </div>
          </div>
          <div className="voice-eq voice-eq-bottom" aria-hidden="true">
            {meterBars.slice(0, 12).map((bar) => (
              <span
                key={`bottom-${bar}`}
                className="voice-eq-bar"
                style={{ animationDelay: `${bar * 80}ms` }}
              />
            ))}
          </div>
        </div>
        <div className="voice-copy">
          <p className="voice-kicker">{transcriptHeadline}</p>
          <h3 className="voice-headline">
            {isRecording ? "The room is listening." : isConnecting ? "Linking to the live stream." : "Tap the orb to speak."}
          </h3>
          <p className="voice-status-line">{statusMessage}</p>
          <div className="voice-live-chip">
            <span className="voice-live-dot" />
            <span>{transcriptPreview || "Speak to see the transcript wake up here."}</span>
          </div>
          {llmResponse ? <p className="voice-ghost-note">{llmResponse}</p> : null}
        </div>
      </div>
      <div className="voice-readout-grid voice-readout-grid-simplified">
        <div className="transcript-preview transcript-preview-live transcript-preview-hero">
          <p className="label">{liveTranscript ? "Live transcript" : "Latest captured response"}</p>
          <p>
            {transcriptPreview || "Your spoken response will appear here once the microphone stream starts."}
          </p>
        </div>
      </div>
      <div className="button-row">
        {isRecording || isConnecting ? (
          <button type="button" className="button" onClick={stopRecording}>
            Stop recording
          </button>
        ) : null}
        <button type="button" className="button secondary" onClick={clearTranscript}>
          Clear transcript
        </button>
      </div>
    </section>
  );
}
