"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  getFollowUpTask,
  getPatient,
  getVisit,
  type FollowUpTask,
  type Patient,
  type ScheduledVisit,
} from "@/lib/api";

export default function FollowUpDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [task, setTask] = useState<FollowUpTask | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [visit, setVisit] = useState<ScheduledVisit | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;

    getFollowUpTask(id)
      .then(async (taskData) => {
        setTask(taskData);
        const [patientData, visitData] = await Promise.all([
          getPatient(taskData.patient_id),
          getVisit(taskData.visit_id),
        ]);
        setPatient(patientData);
        setVisit(visitData);
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="page">
        <div className="loading">Loading follow-up detail...</div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="page">
        <div className="empty">Task not found.</div>
      </div>
    );
  }

  return (
    <div className="page">
      <Link href="/followups" className="back-link">
        ← Back to follow-up queue
      </Link>

      <section className="panel">
        <div className="section-head">
          <div>
            <div className="eyebrow">Follow-Up Task · {task.task_id}</div>
            <h2>{patient ? `${patient.first_name} ${patient.last_name}` : task.patient_id}</h2>
          </div>
          <span className={`badge ${task.status === "completed" ? "badge-completed" : "badge-assigned"}`}>
            {task.status}
          </span>
        </div>

        <div className="detail-grid" style={{ marginTop: "1rem" }}>
          <div className="detail-item">
            <div className="detail-label">Scheduled</div>
            <div className="detail-value">{new Date(task.scheduled_at).toLocaleString()}</div>
          </div>
          <div className="detail-item">
            <div className="detail-label">Created</div>
            <div className="detail-value">{new Date(task.created_at).toLocaleDateString()}</div>
          </div>
          {visit ? (
            <>
              <div className="detail-item">
                <div className="detail-label">Linked Visit</div>
                <div className="detail-value">
                  <Link href={`/visits/${visit.visit_id}`} className="text-link">
                    {visit.visit_date} - {visit.reason}
                  </Link>
                </div>
              </div>
              <div className="detail-item">
                <div className="detail-label">Provider</div>
                <div className="detail-value">{visit.provider_name}</div>
              </div>
            </>
          ) : null}
          {patient ? (
            <>
              <div className="detail-item">
                <div className="detail-label">Patient Phone</div>
                <div className="detail-value">{patient.phone}</div>
              </div>
              <div className="detail-item">
                <div className="detail-label">Insurance</div>
                <div className="detail-value">{patient.insurance_provider ?? "-"}</div>
              </div>
            </>
          ) : null}
        </div>
      </section>

      <section className="panel">
        <div className="eyebrow" style={{ marginBottom: "0.75rem" }}>
          Questions ({task.questions.length})
        </div>
        <div className="question-list">
          {task.questions.map((question, index) => (
            <div key={question.question_id} className="question-item" style={{ cursor: "default" }}>
              <div className="pill" style={{ minWidth: "2rem" }}>
                {index + 1}
              </div>
              <div>
                <div className="question-text">{question.text}</div>
                <div className="question-cat">{question.category}</div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
