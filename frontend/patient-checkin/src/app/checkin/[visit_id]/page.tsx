"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getCheckinForms,
  signConsent,
  submitCheckin,
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
      existing.form_names = Array.from(new Set([...existing.form_names, group.form_name]));
      if (existing.prefilled_value == null && field.prefilled_value != null) {
        existing.prefilled_value = field.prefilled_value;
        existing.source = field.source;
        existing.last_confirmed_at = field.last_confirmed_at;
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
  return `Prefilled from prior visit on ${field.last_confirmed_at.slice(0, 10)}`;
}

export default function CheckinPage() {
  const { visit_id } = useParams<{ visit_id: string }>();
  const router = useRouter();
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);

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
  const filledCount = useMemo(
    () => mergedFields.filter((field) => currentValueFor(field).trim()).length,
    [mergedFields, currentValueFor]
  );

  function speakText(text: string) {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setError("Voice playback is not available on this device.");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.96;
    window.speechSynthesis.speak(utterance);
  }

  function startDictation(fieldId: string, onText: (text: string) => void) {
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
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript?.trim() ?? "";
      if (transcript) onText(transcript);
    };
    recognition.onerror = () => setError("Could not transcribe your answer. Please try again or type it.");
    recognition.onend = () => setListeningField((current) => (current === fieldId ? null : current));
    recognitionRef.current = recognition;
    setListeningField(fieldId);
    recognition.start();
  }

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
                onCommit={(value) => setEdits((prev) => ({ ...prev, [field.field_id]: value }))}
              />
            ))}
          </div>

          <div className="btn-row" style={{ marginTop: "2rem" }}>
            <button className="btn btn-primary" onClick={() => setStep(missingFields.length ? "missing" : "sign")}>
              {missingFields.length ? `Continue - ${missingFields.length} question${missingFields.length > 1 ? "s" : ""} remaining →` : "Continue to final review →"}
            </button>
          </div>
        </div>
      ) : null}

      {step === "missing" ? (
        <div className="panel">
          <h2>Complete The Remaining Questions</h2>
          <p style={{ marginBottom: "1.25rem" }}>
            Every remaining question is listed below. You can type, tap the speaker to hear a question, or use the microphone to dictate your answer.
          </p>

          <div className="voice-assistant-card">
            <div>
              <div className="voice-assistant-title">Guided voice fill</div>
              <div className="voice-assistant-copy">
                Use the built-in assistant to move through the remaining questions one by one.
              </div>
            </div>
            <div className="btn-row">
              <button className="btn btn-secondary" type="button" onClick={() => setVoiceGuide((current) => !current)}>
                {voiceGuide ? "Hide voice guide" : "Start voice guide"}
              </button>
              <button className="btn btn-secondary" type="button" onClick={() => speakText(missingFields.map((field, index) => `Question ${index + 1}. ${field.label}.`).join(" "))}>
                Read all questions
              </button>
            </div>
            {voiceGuide && guideField ? (
              <div className="voice-guide-panel">
                <div className="voice-guide-step">Question {guideIndex + 1} of {missingFields.length}</div>
                <div className="voice-guide-question">{guideField.label}</div>
                <div className="btn-row">
                  <button className="btn btn-secondary" type="button" onClick={() => speakText(guideField.label)}>
                    🔊 Speak
                  </button>
                  <button
                    className="btn btn-primary"
                    type="button"
                    onClick={() => startDictation(guideField.field_id, (text) => setAnswers((prev) => ({ ...prev, [guideField.field_id]: text })))}
                  >
                    {listeningField === guideField.field_id ? "Listening..." : "🎤 Answer"}
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
                onSpeak={() => speakText(field.label)}
                onDictate={() => startDictation(field.field_id, (text) => setAnswers((prev) => ({ ...prev, [field.field_id]: text })))}
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
  onCommit,
}: {
  field: MergedField;
  value: string;
  onCommit: (v: string) => void;
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
          {field.needs_confirmation ? <div className="review-flag">Please verify this value</div> : null}
          <button className="btn btn-secondary btn-sm" style={{ marginTop: "0.5rem", width: "fit-content", fontSize: "0.8rem" }} onClick={() => setEditing(true)}>
            Edit
          </button>
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
