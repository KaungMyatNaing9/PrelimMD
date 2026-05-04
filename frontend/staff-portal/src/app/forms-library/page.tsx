"use client";

import { useEffect, useRef, useState } from "react";
import { getTemplates, uploadTemplate, type FormTemplate } from "@/lib/api";

export default function FormsLibraryPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [templates, setTemplates] = useState<FormTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [meta, setMeta] = useState({
    name: "",
    description: "",
    category: "custom_intake",
  });

  async function load() {
    setTemplates(await getTemplates());
  }

  useEffect(() => {
    load()
      .catch(() => setMessage("Could not load form templates."))
      .finally(() => setLoading(false));
  }, []);

  async function handleUpload(file: File) {
    setSaving(true);
    setMessage("");
    try {
      await uploadTemplate(file, meta, file.name);
      await load();
      setMeta({ name: "", description: "", category: "custom_intake" });
      setMessage("Template uploaded and stored in the forms library.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to upload template.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {message ? <section className="card p-4 text-sm text-slate">{message}</section> : null}

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <div className="card overflow-hidden">
          <div className="border-b border-slate-200 px-5 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Template Library</div>
            <h2 className="mt-2 text-2xl font-semibold text-navy">Reusable intake forms</h2>
          </div>

          <div className="divide-y divide-slate-100">
            {loading ? (
              <div className="px-5 py-8 text-sm text-slate">Loading templates...</div>
            ) : templates.length === 0 ? (
              <div className="px-5 py-8 text-sm text-slate">No templates stored yet.</div>
            ) : (
              templates.map((template) => (
                <div key={template.template_id} className="px-5 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="font-semibold text-navy">{template.name}</div>
                      <div className="mt-1 text-sm text-slate">{template.description}</div>
                    </div>
                    <span className="badge bg-teal-soft text-navy">{template.category}</span>
                  </div>
                  <div className="mt-3 text-sm text-slate">{template.fields?.length ?? 0} parsed fields</div>
                </div>
              ))
            )}
          </div>
        </div>

        <section className="card p-5">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Upload Custom Form</div>
          <h2 className="mt-2 text-2xl font-semibold text-navy">Add PDF or photo</h2>
          <p className="mt-2 text-sm text-slate">Nurses can digitize clinic forms here before assigning them to a visit.</p>

          <div className="mt-5 space-y-4">
            <div>
              <label className="field-label">Template Name</label>
              <input className="field-input" value={meta.name} onChange={(event) => setMeta((current) => ({ ...current, name: event.target.value }))} />
            </div>
            <div>
              <label className="field-label">Category</label>
              <input className="field-input" value={meta.category} onChange={(event) => setMeta((current) => ({ ...current, category: event.target.value }))} />
            </div>
            <div>
              <label className="field-label">Description</label>
              <textarea className="field-input min-h-28" value={meta.description} onChange={(event) => setMeta((current) => ({ ...current, description: event.target.value }))} />
            </div>
          </div>

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="mt-5 flex w-full flex-col items-center justify-center rounded-3xl border border-dashed border-teal/40 bg-teal-soft px-6 py-10 text-center transition hover:border-teal hover:bg-white"
          >
            <span className="text-sm font-semibold text-navy">{saving ? "Uploading..." : "Choose PDF or image"}</span>
            <span className="mt-2 text-sm text-slate">The backend will OCR and parse the form into a DB-backed template.</span>
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,image/*"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void handleUpload(file);
              event.target.value = "";
            }}
          />
        </section>
      </section>
    </div>
  );
}
