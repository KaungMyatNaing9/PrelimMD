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
        setPatients(Object.fromEntries(patientData.map((patient) => [patient.patient_id, patient])));
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () => tasks.filter((task) => filter === "all" || task.status === filter),
    [filter, tasks]
  );

  return (
    <div className="space-y-6">
      <section className="card p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-coral">Doctor Workflow</div>
            <h2 className="mt-2 text-2xl font-semibold text-navy">Follow-up queue</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {(["all", "scheduled", "completed"] as const).map((item) => (
              <button key={item} type="button" onClick={() => setFilter(item)} className={filter === item ? "btn-primary" : "btn-secondary"}>
                {item[0].toUpperCase() + item.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate">
              <tr>
                <th className="px-5 py-3 font-semibold">Patient</th>
                <th className="px-5 py-3 font-semibold">Scheduled</th>
                <th className="px-5 py-3 font-semibold">Questions</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-slate">Loading follow-up tasks...</td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-slate">No follow-up tasks found.</td>
                </tr>
              ) : (
                filtered.map((task) => {
                  const patient = patients[task.patient_id];
                  return (
                    <tr key={task.task_id} className="border-t border-slate-100">
                      <td className="px-5 py-4 font-semibold text-navy">
                        {patient ? `${patient.first_name} ${patient.last_name}` : task.patient_id}
                      </td>
                      <td className="px-5 py-4 text-slate">{task.scheduled_at.slice(0, 16).replace("T", " ")}</td>
                      <td className="px-5 py-4 text-slate">{task.questions.length}</td>
                      <td className="px-5 py-4">
                        <span className={`badge ${task.flags.length ? "bg-rose-100 text-rose-700" : task.status === "completed" ? "bg-teal-100 text-teal-700" : "bg-slate-100 text-slate-700"}`}>
                          {task.status}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <Link href={`/followups/${task.task_id}`} className="btn-secondary">
                          Open Detail
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
