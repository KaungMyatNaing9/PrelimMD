"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getFollowUpTasks, getPatients, type FollowUpTask, type Patient } from "@/lib/api";

export default function FollowUpsPage() {
  const [tasks, setTasks] = useState<FollowUpTask[]>([]);
  const [patients, setPatients] = useState<Record<string, Patient>>({});
  const [filter, setFilter] = useState<"all" | "scheduled" | "completed">("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getFollowUpTasks(), getPatients()])
      .then(([taskData, patientData]) => {
        setTasks(taskData);
        setPatients(Object.fromEntries(patientData.map((pt) => [pt.patient_id, pt])));
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () => tasks.filter((task) => filter === "all" || task.status === filter),
    [filter, tasks]
  );

  return (
    <div className="page">
      <section className="page-hero">
        <div>
          <div className="eyebrow">Post-Discharge</div>
          <h2>Follow-up calls and recovery outreach.</h2>
          <p>
            Monitor scheduled callbacks, inspect question sets, and keep the care team aligned on
            what still needs patient contact.
          </p>
        </div>
        <div className="page-hero-actions">
          {(["all", "scheduled", "completed"] as const).map((item) => (
            <button
              key={item}
              className={`btn ${filter === item ? "btn-primary" : "btn-secondary"}`}
              onClick={() => setFilter(item)}
              style={{ textTransform: "capitalize" }}
            >
              {item}
            </button>
          ))}
        </div>
      </section>

      <section className="table-card">
        <div className="panel-header" style={{ padding: "1.2rem 1.25rem 0" }}>
          <div>
            <h3>Follow-Up Queue</h3>
            <div className="panel-subtext">
              {filtered.length} visible task{filtered.length === 1 ? "" : "s"} in the current view.
            </div>
          </div>
        </div>

        <div className="visit-list" style={{ padding: "0 1.25rem 1.25rem" }}>
          {loading ? (
            <div className="loading">Loading follow-up calls...</div>
          ) : filtered.length === 0 ? (
            <div className="empty">No follow-up tasks found.</div>
          ) : (
            filtered.map((task) => {
              const patient = patients[task.patient_id];
              const scheduledDate = new Date(task.scheduled_at);

              return (
                <Link key={task.task_id} href={`/followups/${task.task_id}`} style={{ display: "contents" }}>
                  <div className="visit-row">
                    <div className="visit-time">
                      <span>
                        {scheduledDate.toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                      </span>
                      <span className="visit-time-sub">
                        {scheduledDate.toLocaleTimeString("en-US", {
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                    <div>
                      <div className="visit-name">
                        {patient ? `${patient.first_name} ${patient.last_name}` : task.patient_id}
                      </div>
                      <div className="visit-meta">
                        {task.questions.length} questions · linked to visit {task.visit_id}
                      </div>
                    </div>
                    <span className="pill">{task.created_by}</span>
                    <span
                      className={`badge ${
                        task.status === "completed" ? "badge-completed" : "badge-assigned"
                      }`}
                    >
                      {task.status}
                    </span>
                  </div>
                </Link>
              );
            })
          )}
        </div>
      </section>
    </div>
  );
}
