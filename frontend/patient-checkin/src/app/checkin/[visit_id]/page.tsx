"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  getCheckinForms,
  scanCheckinForm,
  signConsent,
  submitCheckin,
  type CheckInField,
  type CheckInFormGroup,
  type CheckInScannedField,
} from "@/lib/api";

type Step = "review" | "missing" | "sign" | "done";

const STEP_LABELS = ["Verify", "Review Form", "Complete Fields", "Sign & Submit"];
const STEP_KEYS: Step[] = ["review", "missing", "sign", "done"];

function StepBar({ current }: { current: Step }) {
  const idx = STEP_KEYS.indexOf(current);
  return (
    <div className="step-list">
      {STEP_LABELS.map((label, i) => (
        <div key={label} className="step-item">
          <div className={`step-dot${i < idx ? " done" : i === idx ? " active" : ""}`}>
            {i < idx ? "✓" : i + 1}
          </div>
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

export default function CheckinPage() {
  const { visit_id } = useParams<{ visit_id: string }>();
  const router = useRouter();

  const [formGroups, setFormGroups] = useState<CheckInFormGroup[]>([]);
  const [step, setStep] = useState<Step>("review");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [scanApplied, setScanApplied] = useState<Record<string, string>>({});
  const [signature, setSignature] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [scanBusy, setScanBusy] = useState(false);
  const [scanMessage, setScanMessage] = useState("");
  const [scanPreview, setScanPreview] = useState<string | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState("");

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!visit_id) return;
    getCheckinForms(visit_id)
      .then((res) => setFormGroups(res.forms))
      .catch(() => setError("Could not load your forms. Please ask a staff member for help."))
      .finally(() => setLoading(false));
  }, [visit_id]);

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const allFields = useMemo(() => formGroups.flatMap((g) => g.fields), [formGroups]);
  const fieldById = useMemo(
    () => Object.fromEntries(allFields.map((field) => [field.field_id, field])),
    [allFields]
  );
  const missingFields = allFields.filter((f) => f.required && f.is_missing);
  const reviewFields = allFields.filter((f) => !f.is_missing);
  const filledCount = reviewFields.length + Object.keys(answers).filter((fieldId) => Boolean(answers[fieldId])).length;
  const remainingCount = allFields.filter(
    (field) => field.is_missing && !(answers[field.field_id] && answers[field.field_id].trim())
  ).length;

  const handleSubmit = async () => {
    setBusy(true);
    setError("");
    try {
      const combined = { ...answers, ...edits };
      await submitCheckin(visit_id, combined);
      setStep("sign");
    } catch {
      setError("Could not save your answers. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const handleSign = async () => {
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
  };

  const applyScannedFields = (scannedFields: CheckInScannedField[]) => {
    const nextAnswers: Record<string, string> = {};
    const nextEdits: Record<string, string> = {};
    const nextApplied: Record<string, string> = {};

    for (const scannedField of scannedFields) {
      const currentField = fieldById[scannedField.field_id];
      if (!currentField) continue;

      const normalizedValue = String(scannedField.value);
      nextApplied[scannedField.field_id] = normalizedValue;

      if (currentField.is_missing) {
        nextAnswers[scannedField.field_id] = normalizedValue;
      } else {
        nextEdits[scannedField.field_id] = normalizedValue;
      }
    }

    setAnswers((prev) => ({ ...prev, ...nextAnswers }));
    setEdits((prev) => ({ ...prev, ...nextEdits }));
    setScanApplied((prev) => ({ ...prev, ...nextApplied }));
  };

  const handleScanBlob = async (file: Blob, filename?: string) => {
    setScanBusy(true);
    setError("");
    setCameraError("");
    try {
      const result = await scanCheckinForm(visit_id, file, filename);
      applyScannedFields(result.scanned_fields);
      setScanMessage(result.message);
      setScanPreview(result.ocr_preview ?? null);
      if (result.scanned_fields.some((field) => fieldById[field.field_id]?.is_missing)) {
        setStep("missing");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Camera scan failed. Please try again.");
    } finally {
      setScanBusy(false);
    }
  };

  const openCamera = async () => {
    setCameraError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("Camera access is not available on this device. You can upload a photo instead.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      streamRef.current = stream;
      setCameraOpen(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch {
      setCameraError("We couldn't access the camera. Please allow camera permissions or upload a photo.");
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setCameraOpen(false);
  };

  const capturePhoto = async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const context = canvas.getContext("2d");
    if (!context) return;

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    if (!blob) {
      setCameraError("We couldn't capture the photo. Please try again.");
      return;
    }

    await handleScanBlob(blob, "camera-capture.jpg");
    stopCamera();
  };

  const handleFileSelected = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await handleScanBlob(file, file.name);
    event.target.value = "";
  };

  const pct = step === "review" ? 25 : step === "missing" ? 60 : step === "sign" ? 85 : 100;

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

      {error && <div className="error-msg">{error}</div>}

      <div className="panel summary-panel">
        <div className="summary-grid">
          <div className="summary-item">
            <div className="summary-kicker">Fields Filled</div>
            <div className="summary-value">{filledCount}</div>
          </div>
          <div className="summary-item">
            <div className="summary-kicker">Still Remaining</div>
            <div className="summary-value">{remainingCount}</div>
          </div>
          <div className="summary-item">
            <div className="summary-kicker">Forms</div>
            <div className="summary-value">{formGroups.length}</div>
          </div>
        </div>
      </div>

      <div className="panel scanner-panel">
        <div className="scanner-head">
          <div>
            <div className="section-label">Camera Scan</div>
            <h2 style={{ marginBottom: "0.35rem" }}>Scan a paper form or insurance card</h2>
            <p>
              Hold the document up to the camera and we&apos;ll pull in anything we can. You&apos;ll still
              review every value before submission.
            </p>
          </div>
        </div>

        <div className="btn-row" style={{ marginTop: "1rem" }}>
          <button className="btn btn-primary" type="button" onClick={openCamera} disabled={scanBusy || cameraOpen}>
            {cameraOpen ? "Camera Ready" : "Open camera"}
          </button>
          <button
            className="btn btn-secondary"
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={scanBusy}
          >
            Upload photo instead
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            style={{ display: "none" }}
            onChange={handleFileSelected}
          />
        </div>

        {cameraError ? <div className="error-msg" style={{ marginTop: "1rem" }}>{cameraError}</div> : null}

        {cameraOpen ? (
          <div className="camera-stage">
            <video ref={videoRef} className="camera-video" playsInline muted />
            <canvas ref={canvasRef} style={{ display: "none" }} />
            <div className="btn-row" style={{ marginTop: "1rem" }}>
              <button className="btn btn-primary" type="button" onClick={capturePhoto} disabled={scanBusy}>
                {scanBusy ? "Scanning..." : "Capture and scan"}
              </button>
              <button className="btn btn-secondary" type="button" onClick={stopCamera}>
                Close camera
              </button>
            </div>
          </div>
        ) : null}

        {scanMessage ? <div className="helper-note" style={{ marginTop: "1rem" }}>{scanMessage}</div> : null}
        {scanPreview ? (
          <div className="ocr-preview">
            <div className="section-label">OCR Preview</div>
            <pre>{scanPreview}</pre>
          </div>
        ) : null}
      </div>

      {step === "review" && (
        <div className="panel">
          <h2>Review Your Information</h2>
          <p style={{ marginBottom: "1.5rem" }}>
            We pre-filled these fields from your existing records. Review each one and correct
            anything that looks wrong.
          </p>

          {reviewFields.length === 0 ? (
            <div style={{ color: "var(--text-soft)", padding: "1rem 0" }}>No prefilled fields found.</div>
          ) : (
            <div className="field-review-list">
              {reviewFields.map((field) => (
                <FieldReviewCard
                  key={field.field_id}
                  field={field}
                  editValue={edits[field.field_id]}
                  scannedValue={scanApplied[field.field_id]}
                  onEdit={(value) => setEdits((prev) => ({ ...prev, [field.field_id]: value }))}
                />
              ))}
            </div>
          )}

          <div className="btn-row" style={{ marginTop: "2rem" }}>
            <button
              className="btn btn-primary"
              onClick={() => (missingFields.length > 0 ? setStep("missing") : setStep("sign"))}
            >
              {missingFields.length > 0
                ? `Continue - ${missingFields.length} field${missingFields.length > 1 ? "s" : ""} remaining →`
                : "All good - Continue →"}
            </button>
          </div>
        </div>
      )}

      {step === "missing" && (
        <div className="panel">
          <h2>Complete Your Form</h2>
          <p style={{ marginBottom: "1.5rem" }}>
            Please answer these {missingFields.length} question{missingFields.length > 1 ? "s" : ""} so we can prepare for your visit.
          </p>

          <div className="form-grid">
            {missingFields.map((field) => (
              <MissingFieldInput
                key={field.field_id}
                field={field}
                value={answers[field.field_id] ?? ""}
                scannedValue={scanApplied[field.field_id]}
                onChange={(value) => setAnswers((prev) => ({ ...prev, [field.field_id]: value }))}
              />
            ))}
          </div>

          <div className="btn-row" style={{ marginTop: "2rem" }}>
            <button className="btn btn-secondary" onClick={() => setStep("review")}>
              ← Back
            </button>
            <button className="btn btn-primary" onClick={handleSubmit} disabled={busy}>
              {busy ? "Saving..." : "Save & Continue →"}
            </button>
          </div>
        </div>
      )}

      {step === "sign" && (
        <div className="panel">
          <h2>Consent & Signature</h2>
          <p style={{ marginBottom: "1.5rem" }}>
            By signing below, you confirm that the information you&apos;ve provided is accurate and
            you consent to treatment at this facility.
          </p>

          <div className="sig-wrap">
            <input
              className="sig-input"
              placeholder="Type your full legal name..."
              value={signature}
              onChange={(e) => setSignature(e.target.value)}
              autoComplete="name"
            />
            <div className="sig-hint">Your typed name serves as your electronic signature.</div>
          </div>

          <div className="btn-row" style={{ marginTop: "2rem" }}>
            <button className="btn btn-secondary" onClick={() => setStep(missingFields.length > 0 ? "missing" : "review")}>
              ← Back
            </button>
            <button className="btn btn-primary" onClick={handleSign} disabled={busy || !signature.trim()}>
              {busy ? "Submitting..." : "Submit & Complete Check-In ✓"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function FieldReviewCard({
  field,
  editValue,
  scannedValue,
  onEdit,
}: {
  field: CheckInField;
  editValue?: string;
  scannedValue?: string;
  onEdit: (v: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const displayVal = editValue ?? scannedValue ?? (field.prefilled_value != null ? String(field.prefilled_value) : "");

  return (
    <div className={`field-card${field.needs_review ? " needs-review" : ""}${scannedValue ? " scanned" : ""}`}>
      <div className="field-label">{field.label}</div>
      {editing ? (
        <input
          className="field-edit-input"
          value={editValue ?? displayVal}
          onChange={(e) => onEdit(e.target.value)}
          onBlur={() => setEditing(false)}
          autoFocus
        />
      ) : (
        <>
          <div className={`field-value${!displayVal ? " empty" : ""}`}>{displayVal || "Not provided"}</div>
          {field.needs_review && <div className="review-flag">Please verify this value</div>}
          {scannedValue ? <div className="scan-flag">Updated from camera scan</div> : null}
          <button
            className="btn btn-secondary btn-sm"
            style={{ marginTop: "0.5rem", width: "fit-content", fontSize: "0.8rem" }}
            onClick={() => setEditing(true)}
          >
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
  scannedValue,
  onChange,
}: {
  field: CheckInField;
  value: string;
  scannedValue?: string;
  onChange: (v: string) => void;
}) {
  if (field.type === "boolean") {
    return (
      <div className="field">
        <label>
          {field.label}
          {field.required && <span style={{ color: "var(--danger)" }}> *</span>}
        </label>
        {scannedValue ? <div className="scan-flag">Suggested from camera: {scannedValue}</div> : null}
        <div className="btn-row">
          {["Yes", "No"].map((opt) => (
            <button
              key={opt}
              type="button"
              className={`btn ${value === opt.toLowerCase() ? "btn-primary" : "btn-secondary"}`}
              onClick={() => onChange(opt.toLowerCase())}
              style={{ minWidth: "7rem" }}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (field.type === "number") {
    return (
      <div className="field">
        <label>
          {field.label}
          {field.required && <span style={{ color: "var(--danger)" }}> *</span>}
        </label>
        {scannedValue ? <div className="scan-flag">Suggested from camera: {scannedValue}</div> : null}
        <input
          type="number"
          className={`input${value ? " has-value" : ""}`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          min={0}
          max={10}
          placeholder="0-10"
        />
      </div>
    );
  }

  if (field.type === "date") {
    return (
      <div className="field">
        <label>
          {field.label}
          {field.required && <span style={{ color: "var(--danger)" }}> *</span>}
        </label>
        {scannedValue ? <div className="scan-flag">Suggested from camera: {scannedValue}</div> : null}
        <input
          type="date"
          className={`input${value ? " has-value" : ""}`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
    );
  }

  return (
    <div className="field">
      <label>
        {field.label}
        {field.required && <span style={{ color: "var(--danger)" }}> *</span>}
      </label>
      {scannedValue ? <div className="scan-flag">Suggested from camera: {scannedValue}</div> : null}
      <input
        type={field.type === "email" ? "email" : field.type === "phone" ? "tel" : "text"}
        className={`input${value ? " has-value" : ""}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={`Enter ${field.label.toLowerCase()}...`}
        autoComplete={field.type === "email" ? "email" : field.type === "phone" ? "tel" : "off"}
      />
    </div>
  );
}
