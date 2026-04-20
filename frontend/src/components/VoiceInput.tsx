"use client";

import { useEffect, useRef, useState } from "react";

type BrowserSpeechRecognitionResult = {
  isFinal: boolean;
  0: {
    transcript: string;
  };
};

type BrowserSpeechRecognitionEvent = {
  resultIndex: number;
  results: ArrayLike<BrowserSpeechRecognitionResult>;
};

type BrowserSpeechRecognitionErrorEvent = {
  error: string;
};

type BrowserSpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null;
  onerror: ((event: BrowserSpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
};

type BrowserSpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

type VoiceInputProps = {
  disabled?: boolean;
  onTranscriptCaptured: (transcript: string) => void;
};

function getSpeechRecognitionConstructor() {
  if (typeof window === "undefined") {
    return null;
  }

  const browserWindow = window as Window & {
    SpeechRecognition?: BrowserSpeechRecognitionConstructor;
    webkitSpeechRecognition?: BrowserSpeechRecognitionConstructor;
  };

  return browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition ?? null;
}

export default function VoiceInput({
  disabled = false,
  onTranscriptCaptured,
}: VoiceInputProps) {
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const isRecordingRef = useRef(false);
  const finalTranscriptRef = useRef("");

  const [isSupported, setIsSupported] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [statusMessage, setStatusMessage] = useState(
    "Click the mic to record your real voice in supported browsers."
  );

  useEffect(() => {
    const SpeechRecognition = getSpeechRecognitionConstructor();

    if (!SpeechRecognition) {
      setIsSupported(false);
      setStatusMessage(
        "Speech recognition is not available here. Use Chrome for live voice capture."
      );
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      let finalizedTranscript = finalTranscriptRef.current;
      let interimTranscript = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result[0]?.transcript?.trim();

        if (!transcript) {
          continue;
        }

        if (result.isFinal) {
          finalizedTranscript = `${finalizedTranscript} ${transcript}`.trim();
        } else {
          interimTranscript = `${interimTranscript} ${transcript}`.trim();
        }
      }

      finalTranscriptRef.current = finalizedTranscript;
      setLiveTranscript(`${finalizedTranscript} ${interimTranscript}`.trim());
    };

    recognition.onerror = (event) => {
      isRecordingRef.current = false;
      setIsRecording(false);

      if (event.error === "not-allowed") {
        setStatusMessage("Microphone permission was blocked. Allow mic access and try again.");
        return;
      }

      if (event.error === "no-speech") {
        setStatusMessage("No speech was detected. Try again and speak a little louder.");
        return;
      }

      setStatusMessage(`Voice capture stopped: ${event.error}.`);
    };

    recognition.onend = () => {
      const finalTranscript = finalTranscriptRef.current.trim();
      isRecordingRef.current = false;
      setIsRecording(false);

      if (finalTranscript) {
        setLiveTranscript(finalTranscript);
        setStatusMessage("Transcript captured. Review it and send when ready.");
        onTranscriptCaptured(finalTranscript);
      } else {
        setLiveTranscript("");
        setStatusMessage("Recording ended without a transcript. Try again.");
      }
    };

    recognitionRef.current = recognition;
    setIsSupported(true);

    return () => {
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      recognition.abort();
      recognitionRef.current = null;
    };
  }, [onTranscriptCaptured]);

  function startRecording() {
    if (disabled || !recognitionRef.current || isRecordingRef.current) {
      return;
    }

    finalTranscriptRef.current = "";
    setLiveTranscript("");
    setStatusMessage("Listening... speak clearly, then stop the recording.");
    isRecordingRef.current = true;
    setIsRecording(true);

    try {
      recognitionRef.current.start();
    } catch {
      isRecordingRef.current = false;
      setIsRecording(false);
      setStatusMessage("Recording could not start. Please try again.");
    }
  }

  function stopRecording() {
    if (!recognitionRef.current || !isRecordingRef.current) {
      return;
    }

    setStatusMessage("Stopping recording and finalizing transcript...");
    recognitionRef.current.stop();
  }

  function clearTranscript() {
    if (recognitionRef.current && isRecordingRef.current) {
      recognitionRef.current.abort();
    }

    finalTranscriptRef.current = "";
    isRecordingRef.current = false;
    setIsRecording(false);
    setLiveTranscript("");
    setStatusMessage(
      isSupported
        ? "Transcript cleared. Click the mic when you want to record again."
        : "Speech recognition is not available here. Type into the response box instead."
    );
  }

  function toggleRecording() {
    if (!isSupported) {
      setStatusMessage(
        "Speech recognition is not available in this browser. Chrome usually works best."
      );
      return;
    }

    if (isRecording) {
      stopRecording();
      return;
    }

    startRecording();
  }

  return (
    <section className="panel voice-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Voice capture</p>
          <h2>Mic and transcript preview</h2>
        </div>
        <span className={`status-badge ${isRecording ? "status-live" : "status-idle"}`}>
          {isRecording ? "Recording" : isSupported ? "Ready" : "Unavailable"}
        </span>
      </div>
      <div className="voice-orb-row">
        <button
          type="button"
          className={`voice-orb ${isRecording ? "voice-orb-active" : ""}`}
          disabled={disabled}
          onClick={toggleRecording}
        >
          <span className="voice-orb-core">{isRecording ? "Stop" : "Mic"}</span>
        </button>
        <div className="voice-copy">
          <p className="supporting-text">{statusMessage}</p>
          <p className="muted-text">
            {isSupported
              ? "The captured transcript will be placed into the patient response box."
              : "Live speech recognition depends on browser support and microphone permission."}
          </p>
        </div>
      </div>
      <div className="transcript-preview">
        <p className="label">Live transcript</p>
        <p>{liveTranscript || "Transcript text appears here while you speak."}</p>
      </div>
      <div className="button-row">
        {isRecording ? (
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
