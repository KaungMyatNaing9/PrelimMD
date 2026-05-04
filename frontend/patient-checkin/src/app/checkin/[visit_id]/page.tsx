"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createVoiceAssistantSocket,
  getCheckinForms,
  signConsent,
  submitCheckin,
  synthesizeVoice,
  type VoiceAssistantSocketEvent,
  type CheckInField,
  type CheckInFormGroup,
} from "@/lib/api";

type Step = "review" | "missing" | "sign" | "done";
type BrowserSpeechRecognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: { results?: ArrayLike<ArrayLike<{ transcript?: string }>> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type SpeechRecognitionCtor = new () => BrowserSpeechRecognition;
type MergedField = CheckInField & { form_names: string[] };
type VoiceMessage = { role: "assistant" | "patient"; text: string };
type AssistantState = "idle" | "speaking" | "listening" | "thinking";
type PaceMode = "guided" | "quick";
type AssistantPlan = {
  field_ids: string[];
  prompt: string;
  help_text: string;
  speed_hint?: "fast" | "steady" | "slow";
};

const STEP_LABELS = ["Verify", "Review Form", "Complete Fields", "Sign & Submit"];
const STEP_KEYS: Step[] = ["review", "missing", "sign", "done"];
const NON_FORM_FIELDS = new Set(["consent_signature", "consent_date"]);

function StepBar({ current }: { current: Step }) {
  const idx = STEP_KEYS.indexOf(current);
  return (
    <div className="step-list">
      {STEP_LABELS.map((label, i) => (
        <div key={label} className="step-item">
          <div className={`step-dot${i < idx ? " done" : i === idx ? " active" : ""}`}>{i < idx ? "✓" : i + 1}</div>
          <div className={`step-label${i === idx ? " active" : ""}`}>{label}</div>
        </div>
      ))}
    </div>
  );
}

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="progress-wrap">
      <div className="progress-label">
        <span>Progress</span>
        <span>{pct}%</span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function mergeFormGroups(groups: CheckInFormGroup[]): MergedField[] {
  const merged = new Map<string, MergedField>();
  for (const group of groups) {
    for (const field of group.fields) {
      const existing = merged.get(field.field_id);
      if (!existing) {
        merged.set(field.field_id, { ...field, form_names: [group.form_name] });
        continue;
      }
      existing.required = existing.required || field.required;
      existing.needs_confirmation = existing.needs_confirmation || field.needs_confirmation;
      existing.is_missing = existing.is_missing && field.is_missing;
      existing.is_stale = existing.is_stale || field.is_stale;
      existing.form_names = Array.from(new Set([...existing.form_names, group.form_name]));
      if (existing.prefilled_value == null && field.prefilled_value != null) {
        existing.prefilled_value = field.prefilled_value;
        existing.source = field.source;
        existing.last_confirmed_at = field.last_confirmed_at;
        existing.is_stale = field.is_stale;
      }
      if (!existing.last_confirmed_at && field.last_confirmed_at) {
        existing.last_confirmed_at = field.last_confirmed_at;
      }
    }
  }
  return Array.from(merged.values());
}

function confirmedLabel(field: MergedField) {
  if (!field.last_confirmed_at) return "";
  const date = field.last_confirmed_at.slice(0, 10);
  return field.is_stale
    ? `Last confirmed on ${date}. Please re-check before continuing.`
    : `Prefilled from prior visit on ${date}`;
}

function questionPrompt(field: MergedField) {
  switch (field.field_id) {
    case "full_name":
      return "Could you tell me your full name as it appears on your records?";
    case "date_of_birth":
      return "What is your date of birth?";
    case "gender":
      return "How would you like your gender listed on this form?";
    case "phone":
      return "What is the best phone number for the clinic to reach you?";
    case "email":
      return "What email address should we use for your records?";
    case "address":
      return "What is your current home address?";
    case "insurance_provider":
      return "Which insurance plan are you using for this visit?";
    case "insurance_id":
      return "What is your insurance member ID or policy number?";
    case "emergency_contact_name":
      return "Who should we contact in an emergency?";
    case "emergency_contact_phone":
      return "What is the best phone number for that emergency contact?";
    case "emergency_contact_relation":
      return "What is that person's relationship to you?";
    case "reason_for_visit":
      return "In a few words, what brings you in for this visit?";
    case "current_medications":
      return "Please tell me about the medications you are currently taking.";
    case "known_allergies":
      return "Do you have any allergies we should list for this visit?";
    case "conditions":
      return "Are there any medical conditions or diagnoses we should have on this form?";
    default:
      return field.label.endsWith("?") ? field.label : `${field.label}?`;
  }
}

function questionHelp(field: MergedField) {
  switch (field.field_id) {
    case "insurance_id":
      return "You can usually find this on the front of your insurance card. It may also be called member ID or subscriber ID.";
    case "current_medications":
      return "You can say the medication names only, or include dose and how often you take them if you know that.";
    case "known_allergies":
      return "You can include medicine allergies, food allergies, or anything that has caused a reaction before.";
    case "conditions":
      return "Examples include diabetes, asthma, high blood pressure, or any diagnosis your care team should know about.";
    case "reason_for_visit":
      return "A short summary is enough, such as chest pain follow-up, knee pain, or annual physical.";
    default:
      return `You can answer in your own words. We will place your response into ${field.label.toLowerCase()}.`;
  }
}

export default function CheckinPage() {
  const { visit_id } = useParams<{ visit_id: string }>();
  const router = useRouter();
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const lastAskedFieldRef = useRef<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const assistantSocketRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const suppressMicRef = useRef(false);
  const pendingVoiceCaptureRef = useRef<{
    fieldId: string;
    onText: (text: string) => void;
    autoAdvance?: boolean;
    echoPatient?: boolean;
    field?: MergedField | null;
  } | null>(null);

  const [formGroups, setFormGroups] = useState<CheckInFormGroup[]>([]);
  const [step, setStep] = useState<Step>("review");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [signature, setSignature] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [listeningField, setListeningField] = useState<string | null>(null);
  const [guideIndex, setGuideIndex] = useState(0);
  const [voiceGuide, setVoiceGuide] = useState(false);
  const [reviewConfirmed, setReviewConfirmed] = useState<Record<string, boolean>>({});
  const [voiceMessages, setVoiceMessages] = useState<VoiceMessage[]>([]);
  const [assistantState, setAssistantState] = useState<AssistantState>("idle");
  const [paceMode, setPaceMode] = useState<PaceMode>("quick");
  const [liveTranscript, setLiveTranscript] = useState("");
  const [assistantReady, setAssistantReady] = useState(false);
  const [assistantPlan, setAssistantPlan] = useState<AssistantPlan | null>(null);
  const [handsFreeActive, setHandsFreeActive] = useState(false);

  const assistantPromptFor = useCallback((field: MergedField | null) => {
    if (!field) return "";
    if (assistantPlan && assistantPlan.field_ids.includes(field.field_id)) {
      return assistantPlan.prompt;
    }
    return questionPrompt(field);
  }, [assistantPlan]);

  const assistantHelpFor = useCallback((field: MergedField | null) => {
    if (!field) return "";
    if (assistantPlan && assistantPlan.field_ids.includes(field.field_id)) {
      return assistantPlan.help_text;
    }
    return questionHelp(field);
  }, [assistantPlan]);

  useEffect(() => {
    if (!visit_id) return;
    getCheckinForms(visit_id)
      .then((res) => setFormGroups(res.forms))
      .catch(() => setError("Could not load your forms. Please ask a staff member for help."))
      .finally(() => setLoading(false));
  }, [visit_id]);

  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      if (audioRef.current) {
        audioRef.current.pause();
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
      assistantSocketRef.current?.close();
      processorRef.current?.disconnect();
      sourceNodeRef.current?.disconnect();
      void audioContextRef.current?.close();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      pendingVoiceCaptureRef.current = null;
      setAssistantState("idle");
      recognitionRef.current?.stop();
    };
  }, []);

  const mergedFields = useMemo(() => mergeFormGroups(formGroups), [formGroups]);

  const currentValueFor = useCallback((field: MergedField) => {
    const edited = edits[field.field_id];
    if (edited != null && edited !== "") return edited;
    const answered = answers[field.field_id];
    if (answered != null && answered !== "") return answered;
    if (field.prefilled_value != null) return String(field.prefilled_value);
    return "";
  }, [answers, edits]);

  const reviewFields = useMemo(
    () => mergedFields.filter((field) => !field.is_missing || field.prefilled_value != null),
    [mergedFields]
  );
  const missingFields = useMemo(
    () =>
      mergedFields.filter(
        (field) =>
          !NON_FORM_FIELDS.has(field.field_id) &&
          (field.is_missing || currentValueFor(field).trim() === "")
      ),
    [mergedFields, currentValueFor]
  );
  const unansweredCount = useMemo(
    () => missingFields.filter((field) => !currentValueFor(field).trim()).length,
    [missingFields, currentValueFor]
  );
  const guideField = missingFields[guideIndex] ?? null;
  const staleFields = useMemo(
    () => reviewFields.filter((field) => field.is_stale),
    [reviewFields]
  );
  const pendingRevalidations = useMemo(
    () =>
      staleFields.filter((field) => {
        const currentValue = currentValueFor(field).trim();
        if (!currentValue) return true;
        return !reviewConfirmed[field.field_id];
      }).length,
    [currentValueFor, reviewConfirmed, staleFields]
  );
  const filledCount = useMemo(
    () => mergedFields.filter((field) => currentValueFor(field).trim()).length,
    [mergedFields, currentValueFor]
  );

  function currentPlanField(): MergedField | null {
    if (!assistantPlan?.field_ids?.length) return guideField;
    return mergedFields.find((field) => field.field_id === assistantPlan.field_ids[0]) ?? guideField;
  }

  function updateAnswersFromAssistant(extracted: Record<string, string>) {
    if (!Object.keys(extracted).length) return;
    setAnswers((prev) => ({ ...prev, ...extracted }));
  }

  const stopBrowserAudioStream = useCallback(() => {
    processorRef.current?.disconnect();
    sourceNodeRef.current?.disconnect();
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    if (audioContextRef.current) {
      void audioContextRef.current.close();
    }
    processorRef.current = null;
    sourceNodeRef.current = null;
    mediaStreamRef.current = null;
    audioContextRef.current = null;
    setListeningField(null);
    setAssistantState("idle");
  }, []);

  function downsampleBuffer(buffer: Float32Array, inputRate: number, outputRate: number) {
    if (outputRate === inputRate) return buffer;
    const ratio = inputRate / outputRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
      let accum = 0;
      let count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i += 1) {
        accum += buffer[i];
        count += 1;
      }
      result[offsetResult] = accum / count;
      offsetResult += 1;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  }

  function floatTo16BitPCM(floatBuffer: Float32Array) {
    const pcmBuffer = new ArrayBuffer(floatBuffer.length * 2);
    const view = new DataView(pcmBuffer);
    for (let i = 0; i < floatBuffer.length; i += 1) {
      const sample = Math.max(-1, Math.min(1, floatBuffer[i]));
      view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    }
    return pcmBuffer;
  }

  const speakText = useCallback(async (text: string) => {
    try {
      suppressMicRef.current = true;
      setAssistantState("speaking");
      const { audioUrl, fallbackText } = await synthesizeVoice(text);
      if (audioUrl) {
        if (audioRef.current) {
          audioRef.current.pause();
        }
        if (audioUrlRef.current) {
          URL.revokeObjectURL(audioUrlRef.current);
        }
        audioUrlRef.current = audioUrl;
        const audio = new Audio(audioUrl);
        audioRef.current = audio;
        audio.onended = () => {
          suppressMicRef.current = false;
          setAssistantState(handsFreeActive ? "listening" : "idle");
        };
        audio.onerror = () => {
          suppressMicRef.current = false;
          setAssistantState(handsFreeActive ? "listening" : "idle");
        };
        await audio.play();
        return;
      }

      if (typeof window === "undefined" || !("speechSynthesis" in window)) {
        suppressMicRef.current = false;
        setError("Voice playback is not available on this device.");
        return;
      }
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(fallbackText);
      const voices = window.speechSynthesis.getVoices();
      const preferredVoice =
        voices.find((voice) => /samantha|ava|allison|google us english/i.test(voice.name)) ||
        voices.find((voice) => /en-us/i.test(voice.lang)) ||
        voices[0];
      if (preferredVoice) utterance.voice = preferredVoice;
      utterance.rate = 0.98;
      utterance.pitch = 1.04;
      utterance.onend = () => {
        suppressMicRef.current = false;
        setAssistantState(handsFreeActive ? "listening" : "idle");
      };
      utterance.onerror = () => {
        suppressMicRef.current = false;
        setAssistantState(handsFreeActive ? "listening" : "idle");
      };
      window.speechSynthesis.speak(utterance);
    } catch {
      suppressMicRef.current = false;
      setAssistantState("idle");
      setError("Voice playback could not be started.");
    }
  }, [handsFreeActive]);

  function sendUtteranceToAssistant(transcript: string, field: MergedField | null) {
    const socket = assistantSocketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN || !field) {
      return;
    }
    socket.send(
      JSON.stringify({
        type: "utterance",
        transcript,
        pace: paceMode,
        field_id: field.field_id,
        field_ids: assistantPlan?.field_ids?.length ? assistantPlan.field_ids : [field.field_id],
        field_label: field.label,
        question: assistantPromptFor(field),
        help_text: assistantHelpFor(field),
        remaining_fields: missingFields.map((item) => ({ field_id: item.field_id, label: item.label, type: item.type })),
      })
    );
  }

  function ensureAssistantSocket() {
    if (assistantSocketRef.current && assistantSocketRef.current.readyState === WebSocket.OPEN) {
      return;
    }
    const socket = createVoiceAssistantSocket();
    assistantSocketRef.current = socket;
    socket.onopen = () => {
      setAssistantReady(true);
      socket.send(JSON.stringify({ type: "ping" }));
      if (voiceGuide && guideField) {
        socket.send(
          JSON.stringify({
            type: "context",
            visit_id,
            pace: paceMode,
            current_field_id: guideField.field_id,
            remaining_fields: missingFields.map((field) => ({
              field_id: field.field_id,
              label: field.label,
              type: field.type,
            })),
          })
        );
      }
    };
    socket.onclose = () => {
      setAssistantReady(false);
    };
    socket.onerror = () => {
      setAssistantReady(false);
    };
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as VoiceAssistantSocketEvent;
        if (payload.type === "pong") {
          setAssistantReady(true);
          return;
        }
        if (payload.type === "plan") {
          setAssistantPlan({
            field_ids: payload.field_ids,
            prompt: payload.prompt,
            help_text: payload.help_text,
            speed_hint: payload.speed_hint,
          });
          return;
        }
        if (payload.type === "assistant") {
          if (payload.transcript?.trim()) {
            setLiveTranscript(payload.transcript.trim());
          }
          const pending = pendingVoiceCaptureRef.current;
          if (payload.transcript?.trim() && (handsFreeActive || pending?.echoPatient)) {
            setVoiceMessages((current) => [...current, { role: "patient", text: payload.transcript.trim() }]);
          }
          setVoiceMessages((current) => [...current, { role: "assistant", text: payload.reply }]);
          updateAnswersFromAssistant(payload.extracted_answers || {});

          if (pending && payload.transcript?.trim()) {
            pending.onText(payload.transcript.trim());
            if (!Object.keys(payload.extracted_answers || {}).length && pending.field) {
              const fallbackFieldId = pending.field.field_id;
              setAnswers((prev) => ({ ...prev, [fallbackFieldId]: payload.transcript.trim() }));
            }
          }

          const consumed = payload.consumed_field_ids?.length
            ? payload.consumed_field_ids
            : Object.keys(payload.extracted_answers || {});
          if ((handsFreeActive || pending?.autoAdvance) && consumed.length) {
            setGuideIndex((current) => Math.min(missingFields.length - 1, current + Math.max(1, consumed.length)));
          } else if ((handsFreeActive || pending?.autoAdvance) && missingFields.length > 1) {
            setGuideIndex((current) => Math.min(missingFields.length - 1, current + 1));
          }

          if (pending && !handsFreeActive) {
            stopBrowserAudioStream();
            pendingVoiceCaptureRef.current = null;
          }
          if (paceMode === "guided" || payload.should_repeat || payload.speed_hint === "slow") {
            void speakText(payload.reply);
          } else {
            setAssistantState(handsFreeActive ? "listening" : "idle");
          }
          return;
        }
        if (payload.type === "partial") {
          setLiveTranscript(payload.transcript);
          return;
        }
        if (payload.type === "error") {
          if (handsFreeActive) {
            setAssistantState("listening");
          }
          return;
        }
      } catch {
        // ignore malformed messages
      }
    };
  }

  async function startBrowserAudioStream(activeFieldId: string) {
    ensureAssistantSocket();
    if (mediaStreamRef.current && audioContextRef.current && processorRef.current) {
      setListeningField(activeFieldId);
      setAssistantState("listening");
      return true;
    }

    try {
      recognitionRef.current?.stop();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);

      mediaStreamRef.current = stream;
      audioContextRef.current = audioContext;
      sourceNodeRef.current = source;
      processorRef.current = processor;

      setAssistantState("listening");
      setListeningField(activeFieldId);
      setLiveTranscript("");

      processor.onaudioprocess = (event) => {
        const socket = assistantSocketRef.current;
        if (!socket || socket.readyState !== WebSocket.OPEN || suppressMicRef.current) return;
        const input = event.inputBuffer.getChannelData(0);
        const downsampled = downsampleBuffer(input, audioContext.sampleRate, 16000);
        const pcm = floatTo16BitPCM(downsampled);
        socket.send(pcm);
      };

      source.connect(processor);
      processor.connect(audioContext.destination);
      return true;
    } catch {
      setError("Live microphone streaming is not available. Falling back to local dictation.");
      return false;
    }
  }

  function startDictation(fieldId: string, onText: (text: string) => void, options?: { autoAdvance?: boolean; echoPatient?: boolean; field?: MergedField | null }) {
    const field = options?.field ?? null;
    ensureAssistantSocket();
    syncAssistantContext(field);

    if (typeof navigator.mediaDevices?.getUserMedia === "function" && assistantSocketRef.current) {
      void (async () => {
        const started = await startBrowserAudioStream(fieldId);
        if (started) {
          pendingVoiceCaptureRef.current = {
            fieldId,
            onText,
            autoAdvance: options?.autoAdvance,
            echoPatient: options?.echoPatient,
            field,
          };
          return;
        }
      })();
      return;
    }

    const ctor = (window as Window & { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor }).SpeechRecognition
      || (window as Window & { webkitSpeechRecognition?: SpeechRecognitionCtor }).webkitSpeechRecognition;
    if (!ctor) {
      setError("Speech-to-text is not available on this device.");
      return;
    }
    recognitionRef.current?.stop();
    const recognition = new ctor();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    setAssistantState("listening");
    setLiveTranscript("");
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript?.trim() ?? "";
      setLiveTranscript(transcript);
      if (transcript) {
        setAssistantState("thinking");
        onText(transcript);
        if (options?.echoPatient) {
          setVoiceMessages((current) => [
            ...current,
            { role: "patient", text: transcript },
          ]);
        }
        sendUtteranceToAssistant(transcript, field);
        if (options?.autoAdvance) {
          window.setTimeout(() => {
            setGuideIndex((current) => Math.min(missingFields.length - 1, current + 1));
          }, 150);
        }
      }
    };
    recognition.onerror = () => setError("Could not transcribe your answer. Please try again or type it.");
    recognition.onend = () => {
      setListeningField((current) => (current === fieldId ? null : current));
      setAssistantState("idle");
    };
    recognitionRef.current = recognition;
    setListeningField(fieldId);
    recognition.start();
  }

  function markReviewed(fieldId: string) {
    setReviewConfirmed((current) => ({ ...current, [fieldId]: true }));
  }

  const syncAssistantContext = useCallback((targetField: MergedField | null = guideField) => {
    const socket = assistantSocketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN || !targetField) {
      return;
    }
    socket.send(
      JSON.stringify({
        type: "context",
        visit_id,
        pace: paceMode,
        current_field_id: targetField.field_id,
        remaining_fields: missingFields.map((field) => ({
          field_id: field.field_id,
          label: field.label,
          type: field.type,
        })),
      })
    );
  }, [guideField, missingFields, paceMode, visit_id]);

  function startVoiceAssistant() {
    ensureAssistantSocket();
    setVoiceGuide(true);
    setGuideIndex(0);
    lastAskedFieldRef.current = null;
    const firstField = missingFields[0];
    if (!firstField) return;
    const intro = paceMode === "quick"
      ? "Hi, I’m your PrelimMD assistant. I’ll keep this fast and only speak when it helps."
      : "Hi, I’m your PrelimMD assistant. I’ll walk through the remaining questions one at a time. You can answer by voice or type if you prefer.";
    const firstQuestion = assistantPromptFor(firstField);
    lastAskedFieldRef.current = firstField.field_id;
    setVoiceMessages([
      { role: "assistant", text: intro },
      { role: "assistant", text: firstQuestion },
    ]);
    if (paceMode === "guided") {
      void speakText(`${intro} ${firstQuestion}`);
    }
  }

  const stopHandsFreeMode = useCallback(() => {
    setHandsFreeActive(false);
    pendingVoiceCaptureRef.current = null;
    stopBrowserAudioStream();
  }, [stopBrowserAudioStream]);

  function startHandsFreeMode() {
    const firstField = missingFields[0];
    if (!firstField) return;
    startVoiceAssistant();
    lastAskedFieldRef.current = null;
    pendingVoiceCaptureRef.current = null;
    setHandsFreeActive(true);
    void (async () => {
      const started = await startBrowserAudioStream(firstField.field_id);
      if (!started) {
        setHandsFreeActive(false);
      }
    })();
  }

  const askCurrentGuideQuestion = useCallback((field: MergedField) => {
    const prompt = assistantPromptFor(field);
    setVoiceMessages((current) => [...current, { role: "assistant", text: prompt }]);
    void speakText(prompt);
  }, [assistantPromptFor, speakText]);

  useEffect(() => {
    if (!voiceGuide || !guideField) return;
    syncAssistantContext(guideField);
  }, [guideField, syncAssistantContext, voiceGuide]);

  useEffect(() => {
    if (!voiceGuide && handsFreeActive) {
      stopHandsFreeMode();
    }
  }, [handsFreeActive, stopHandsFreeMode, voiceGuide]);

  useEffect(() => {
    if (!voiceGuide || !guideField) return;
    if (lastAskedFieldRef.current === guideField.field_id) return;
    lastAskedFieldRef.current = guideField.field_id;
    if (handsFreeActive || paceMode === "guided") {
      askCurrentGuideQuestion(guideField);
    }
  }, [askCurrentGuideQuestion, guideField, handsFreeActive, paceMode, voiceGuide]);

  useEffect(() => {
    if (!handsFreeActive || !guideField) return;
    setListeningField(guideField.field_id);
    if (assistantState !== "speaking" && assistantState !== "thinking") {
      setAssistantState("listening");
    }
  }, [assistantState, guideField, handsFreeActive]);

  useEffect(() => {
    if (handsFreeActive && missingFields.length === 0) {
      stopHandsFreeMode();
    }
  }, [handsFreeActive, missingFields.length, stopHandsFreeMode]);

  async function handleSaveAndContinue() {
    setBusy(true);
    setError("");
    try {
      await submitCheckin(visit_id, { ...answers, ...edits });
      setStep("sign");
    } catch {
      setError("Could not save your answers. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSign() {
    if (!signature.trim()) {
      setError("Please type your full name to sign.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await signConsent(visit_id, signature);
      router.push("/complete");
    } catch {
      setError("Could not record consent. Please ask a staff member.");
    } finally {
      setBusy(false);
    }
  }

  const pct = step === "review" ? 25 : step === "missing" ? 60 : step === "sign" ? 88 : 100;

  if (loading) {
    return (
      <div className="page">
        <div style={{ textAlign: "center", padding: "3rem", color: "var(--text-soft)" }}>Loading your forms...</div>
      </div>
    );
  }

  return (
    <div className="page">
      <StepBar current={step} />
      <ProgressBar pct={pct} />

      {error ? <div className="error-msg">{error}</div> : null}

      <div className="panel summary-panel">
        <div className="summary-grid">
          <div className="summary-item">
            <div className="summary-kicker">Unique Fields Filled</div>
            <div className="summary-value">{filledCount}</div>
          </div>
          <div className="summary-item">
            <div className="summary-kicker">Still Remaining</div>
            <div className="summary-value">{missingFields.filter((field) => !currentValueFor(field).trim()).length}</div>
          </div>
          <div className="summary-item">
            <div className="summary-kicker">Forms Assigned</div>
            <div className="summary-value">{formGroups.length}</div>
          </div>
        </div>
      </div>

      {step === "review" ? (
        <div className="panel">
          <h2>Review Your Information</h2>
          <p style={{ marginBottom: "1.5rem" }}>
            We merged your assigned forms so duplicate questions only appear once. Please confirm the prefilled information and update anything that has changed.
          </p>

          <div className="field-review-list">
            {reviewFields.map((field) => (
              <FieldReviewCard
                key={field.field_id}
                field={field}
                value={currentValueFor(field)}
                confirmed={Boolean(reviewConfirmed[field.field_id])}
                onCommit={(value) => {
                  setEdits((prev) => ({ ...prev, [field.field_id]: value }));
                  markReviewed(field.field_id);
                }}
                onConfirm={() => markReviewed(field.field_id)}
              />
            ))}
          </div>

          <div className="btn-row" style={{ marginTop: "2rem" }}>
            <button
              className="btn btn-primary"
              onClick={() => setStep(missingFields.length ? "missing" : "sign")}
              disabled={pendingRevalidations > 0}
            >
              {pendingRevalidations > 0
                ? `Confirm ${pendingRevalidations} stale field${pendingRevalidations > 1 ? "s" : ""} first`
                : missingFields.length
                  ? `Continue - ${missingFields.length} question${missingFields.length > 1 ? "s" : ""} remaining →`
                  : "Continue to final review →"}
            </button>
          </div>
        </div>
      ) : null}

      {step === "missing" ? (
        <div className="panel">
          <h2>Complete The Remaining Questions</h2>
          <p style={{ marginBottom: "1.25rem" }}>
            Every remaining question is listed below. You can type, tap the speaker to hear a question, use the microphone for one answer, or start hands-free call mode and answer naturally.
          </p>

          <div className="voice-assistant-card">
            <div>
              <div className="voice-assistant-title">Talk with PrelimMD Assistant</div>
              <div className="voice-assistant-copy">
                Start a conversational intake flow. In quick mode it keeps prompts short and gets out of the way. In guided mode it speaks more and slows down when needed.
              </div>
            </div>
            <div className="pace-toggle" role="group" aria-label="Assistant pace">
              <button className={`btn ${paceMode === "quick" ? "btn-primary" : "btn-secondary"} btn-sm`} type="button" onClick={() => setPaceMode("quick")}>
                Quick mode
              </button>
              <button className={`btn ${paceMode === "guided" ? "btn-primary" : "btn-secondary"} btn-sm`} type="button" onClick={() => setPaceMode("guided")}>
                Guided mode
              </button>
              <span className="pace-status">{assistantReady ? "Live assistant connected" : "Live assistant will connect when started"}</span>
            </div>
            <div className="btn-row">
              <button
                className={`btn ${handsFreeActive ? "btn-primary" : "btn-secondary"}`}
                type="button"
                onClick={() => (handsFreeActive ? stopHandsFreeMode() : startHandsFreeMode())}
              >
                {handsFreeActive ? "Stop hands-free call mode" : "Start hands-free call mode"}
              </button>
              <button className="btn btn-secondary" type="button" onClick={() => (voiceGuide ? setVoiceGuide(false) : startVoiceAssistant())}>
                {voiceGuide ? "Hide assistant panel" : "Open assistant panel"}
              </button>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => speakText(missingFields.map((field, index) => `Question ${index + 1}. ${assistantPromptFor(field)}`).join(" "))}
              >
                Read all questions
              </button>
            </div>
            {voiceGuide && guideField ? (
              <div className="voice-guide-panel">
                <div className="voice-avatar-row">
                  <div className={`voice-avatar ${assistantState !== "idle" ? `is-${assistantState}` : ""}`}>
                    <span>AI</span>
                    <div className="voice-avatar-rings" aria-hidden="true">
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                  <div>
                    <div className="voice-guide-step">Question {guideIndex + 1} of {missingFields.length}</div>
                    <div className="voice-guide-question">{assistantPromptFor(guideField)}</div>
                    <div className="voice-guide-status">
                      {handsFreeActive ? "Hands-free call mode is on. Just answer naturally after each prompt." : null}
                      {assistantState === "speaking" ? "Assistant is speaking..." : null}
                      {assistantState === "listening" ? "Assistant is listening..." : null}
                      {assistantState === "thinking" ? "Assistant is saving your answer..." : null}
                      {assistantState === "idle" && !handsFreeActive ? "Assistant is ready." : null}
                    </div>
                    {liveTranscript ? <div className="voice-live-transcript">Heard: {liveTranscript}</div> : null}
                  </div>
                </div>
                <div className="voice-transcript">
                  {voiceMessages.slice(-6).map((message, index) => (
                    <div key={`${message.role}-${index}`} className={`voice-bubble ${message.role}`}>
                      {message.text}
                    </div>
                  ))}
                </div>
                <div className="btn-row">
                  <button className="btn btn-secondary" type="button" onClick={() => askCurrentGuideQuestion(guideField)}>
                    Ask again
                  </button>
                  <button className="btn btn-secondary" type="button" onClick={() => speakText(assistantHelpFor(guideField))}>
                    Explain question
                  </button>
                  <button
                    className="btn btn-primary"
                    type="button"
                    disabled={handsFreeActive}
                    onClick={() =>
                      startDictation(
                        guideField.field_id,
                        (text) => setAnswers((prev) => ({ ...prev, [guideField.field_id]: text })),
                        { autoAdvance: true, echoPatient: true, field: guideField }
                      )
                    }
                  >
                    {handsFreeActive ? "Hands-free is active" : listeningField === guideField.field_id ? "Listening..." : "Answer by voice"}
                  </button>
                  <button className="btn btn-secondary" type="button" onClick={() => setGuideIndex((current) => Math.max(0, current - 1))} disabled={guideIndex === 0}>
                    Previous
                  </button>
                  <button className="btn btn-secondary" type="button" onClick={() => setGuideIndex((current) => Math.min(missingFields.length - 1, current + 1))} disabled={guideIndex >= missingFields.length - 1}>
                    Next
                  </button>
                </div>
              </div>
            ) : null}
          </div>

          <div className="form-grid">
            {missingFields.map((field) => (
              <MissingFieldInput
                key={field.field_id}
                field={field}
                value={currentValueFor(field)}
                listening={listeningField === field.field_id}
                onChange={(value) => setAnswers((prev) => ({ ...prev, [field.field_id]: value }))}
                onSpeak={() => speakText(questionPrompt(field))}
                onDictate={() => startDictation(field.field_id, (text) => setAnswers((prev) => ({ ...prev, [field.field_id]: text })), { field })}
              />
            ))}
          </div>

          <div className="btn-row" style={{ marginTop: "2rem" }}>
            <button className="btn btn-secondary" onClick={() => setStep("review")}>
              ← Back
            </button>
            <button className="btn btn-primary" onClick={handleSaveAndContinue} disabled={busy || unansweredCount > 0}>
              {busy ? "Saving..." : unansweredCount > 0 ? `Complete ${unansweredCount} remaining field${unansweredCount > 1 ? "s" : ""}` : "Save & Continue →"}
            </button>
          </div>
        </div>
      ) : null}

      {step === "sign" ? (
        <div className="panel">
          <h2>Final Review Before Signing</h2>
          <p style={{ marginBottom: "1.5rem" }}>
            This is the final merged form view. If something is wrong, go back and change it before signing.
          </p>

          <div className="voice-assistant-card" style={{ marginBottom: "1.5rem" }}>
            <div>
              <div className="voice-assistant-title">Final AI-ready review</div>
              <div className="voice-assistant-copy">
                This is the completed form data that will be stored for staff review. Use the speaker buttons to hear answers back before signing.
              </div>
            </div>
          </div>

          <div className="final-review-grid">
            {mergedFields
              .filter((field) => !NON_FORM_FIELDS.has(field.field_id))
              .map((field) => (
                <div key={field.field_id} className="final-review-card">
                  <div className="final-review-top">
                    <div>
                      <div className="field-label">{field.label}</div>
                      <div className="final-review-meta">{field.form_names.join(" • ")}</div>
                    </div>
                    <button className="icon-btn" type="button" onClick={() => speakText(`${field.label}. ${currentValueFor(field) || "No answer entered."}`)}>
                      🔊
                    </button>
                  </div>
                  <div className={`field-value${!currentValueFor(field) ? " empty" : ""}`}>{currentValueFor(field) || "No answer entered"}</div>
                  {confirmedLabel(field) ? <div className="review-flag subtle">{confirmedLabel(field)}</div> : null}
                </div>
              ))}
          </div>

          <div className="sig-wrap">
            <input
              className="sig-input"
              placeholder="Type your full legal name..."
              value={signature}
              onChange={(event) => setSignature(event.target.value)}
              autoComplete="name"
            />
            <div className="sig-hint">Your typed name will be recorded as your electronic signature.</div>
          </div>

          <div className="btn-row" style={{ marginTop: "2rem" }}>
            <button className="btn btn-secondary" onClick={() => setStep("missing")}>
              ← Back
            </button>
            <button className="btn btn-primary" onClick={handleSign} disabled={busy || !signature.trim()}>
              {busy ? "Submitting..." : "Submit & Complete Check-In ✓"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function FieldReviewCard({
  field,
  value,
  confirmed,
  onCommit,
  onConfirm,
}: {
  field: MergedField;
  value: string;
  confirmed: boolean;
  onCommit: (v: string) => void;
  onConfirm: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  function finishEdit() {
    onCommit(draft);
    setEditing(false);
  }

  return (
    <div className={`field-card${field.needs_confirmation ? " needs-review" : ""}`}>
      <div className="field-label">{field.label}</div>
      <div className="final-review-meta">{field.form_names.join(" • ")}</div>
      {editing ? (
        <div className="edit-row">
          <input
            className="field-edit-input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={finishEdit}
            onKeyDown={(event) => {
              if (event.key === "Enter") finishEdit();
              if (event.key === "Escape") {
                setDraft(value);
                setEditing(false);
              }
            }}
            autoFocus
          />
          <button className="btn btn-secondary btn-sm" type="button" onClick={finishEdit}>
            Done
          </button>
        </div>
      ) : (
        <>
          <div className={`field-value${!value ? " empty" : ""}`}>{value || "Not provided"}</div>
          {field.last_confirmed_at ? <div className="review-flag subtle">{confirmedLabel(field)}</div> : null}
          {field.needs_confirmation ? (
            <div className={`review-flag${field.is_stale ? " stale" : ""}`}>
              {field.is_stale ? "This saved value is older and must be revalidated." : "Please verify this value"}
            </div>
          ) : null}
          <div className="btn-row" style={{ marginTop: "0.5rem" }}>
            <button className="btn btn-secondary btn-sm" style={{ width: "fit-content", fontSize: "0.8rem" }} onClick={() => setEditing(true)}>
              Edit
            </button>
            {field.is_stale ? (
              <button className={`btn btn-sm ${confirmed ? "btn-primary" : "btn-secondary"}`} type="button" style={{ width: "fit-content", fontSize: "0.8rem" }} onClick={onConfirm}>
                {confirmed ? "Revalidated" : "Confirm current"}
              </button>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}

function MissingFieldInput({
  field,
  value,
  listening,
  onChange,
  onSpeak,
  onDictate,
}: {
  field: MergedField;
  value: string;
  listening: boolean;
  onChange: (v: string) => void;
  onSpeak: () => void;
  onDictate: () => void;
}) {
  const header = (
    <div className="question-header">
      <label>
        {field.label}
        {field.required ? <span style={{ color: "var(--danger)" }}> *</span> : null}
      </label>
      <div className="question-tools">
        <button className="icon-btn" type="button" onClick={onSpeak}>🔊</button>
        <button className="icon-btn" type="button" onClick={onDictate}>{listening ? "…" : "🎤"}</button>
      </div>
    </div>
  );

  if (field.type === "boolean") {
    return (
      <div className="field">
        {header}
        <div className="btn-row">
          {["yes", "no"].map((opt) => (
            <button key={opt} type="button" className={`btn ${value === opt ? "btn-primary" : "btn-secondary"}`} onClick={() => onChange(opt)} style={{ minWidth: "7rem" }}>
              {opt[0].toUpperCase() + opt.slice(1)}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="field">
      {header}
      <input
        type={field.type === "email" ? "email" : field.type === "phone" ? "tel" : field.type === "date" ? "date" : field.type === "number" ? "number" : "text"}
        className={`input${value ? " has-value" : ""}`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={`Enter ${field.label.toLowerCase()}...`}
        autoComplete={field.type === "email" ? "email" : field.type === "phone" ? "tel" : "off"}
      />
      <div className="final-review-meta">{field.form_names.join(" • ")}</div>
    </div>
  );
}
