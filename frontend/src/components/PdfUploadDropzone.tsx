"use client";

import { useRouter } from "next/navigation";
import { DragEvent, useRef, useState } from "react";
import { isMockApiEnabled, resetInterview, startInterview, uploadFormPdf } from "@/lib/api";

type UploadState = "idle" | "parsing" | "error";

export default function PdfUploadDropzone() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setErrorMessage("Only PDF files are accepted.");
      setUploadState("error");
      return;
    }

    setUploadState("parsing");
    setErrorMessage(null);

    try {
      const { form_id } = await uploadFormPdf(file);
      await resetInterview();
      await startInterview(form_id);
      router.push("/interview");
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "Something went wrong during upload."
      );
      setUploadState("error");
    }
  }

  function onDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragOver(true);
  }

  function onDragLeave() {
    setIsDragOver(false);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function onInputChange() {
    const file = inputRef.current?.files?.[0];
    if (file) handleFile(file);
  }

  function reset() {
    setUploadState("idle");
    setErrorMessage(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  if (isMockApiEnabled) {
    return (
      <div className="dropzone dropzone--notice">
        <p className="dropzone__label">PDF upload requires the live backend.</p>
        <p className="dropzone__sub">
          Set <code>NEXT_PUBLIC_USE_MOCK_API=false</code> and start the FastAPI server to use this
          feature.
        </p>
      </div>
    );
  }

  if (uploadState === "parsing") {
    return (
      <div className="dropzone dropzone--parsing">
        <span className="dropzone__spinner" aria-hidden="true" />
        <p className="dropzone__label">Parsing form with AI...</p>
        <p className="dropzone__sub">This typically takes 20–40 seconds. Please wait.</p>
      </div>
    );
  }

  return (
    <div
      className={`dropzone${isDragOver ? " dropzone--over" : ""}${uploadState === "error" ? " dropzone--error" : ""}`}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={() => uploadState !== "error" && inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
      aria-label="Drop a clinical intake PDF or click to browse"
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        className="dropzone__input"
        onChange={onInputChange}
        tabIndex={-1}
      />

      <svg
        className="dropzone__icon"
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="12" y1="18" x2="12" y2="12" />
        <line x1="9" y1="15" x2="15" y2="15" />
      </svg>

      {uploadState === "error" ? (
        <>
          <p className="dropzone__label">{errorMessage}</p>
          <button
            className="button ghost"
            onClick={(e) => {
              e.stopPropagation();
              reset();
            }}
          >
            Try again
          </button>
        </>
      ) : (
        <>
          <p className="dropzone__label">
            {isDragOver ? "Drop to parse" : "Drag a clinical intake PDF here"}
          </p>
          <p className="dropzone__sub">or click to browse your files</p>
        </>
      )}
    </div>
  );
}
