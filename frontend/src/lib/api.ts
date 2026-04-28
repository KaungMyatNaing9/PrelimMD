const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const isMockApiEnabled = process.env.NEXT_PUBLIC_USE_MOCK_API !== "false";

const SESSION_STORAGE_KEY = "prelimmd-demo-session";
const LIVE_SESSION_KEY = "prelimmd-live-session";
const REPORT_STORAGE_KEY = "prelimmd-demo-report";
const BOOKING_STORAGE_KEY = "prelimmd-demo-booking";

const DEMO_QUESTIONS = [
  "Tell me the main reason you're seeking care today.",
  "When did these symptoms start, and are they getting better, worse, or staying the same?",
  "Are you having any red-flag symptoms such as trouble breathing, chest pain, fainting, or severe dehydration?",
  "What outcome would make this visit feel successful for you today?",
] as const;

type InterviewStatus = "in_progress" | "completed";

export type TriageLevel = "low" | "moderate" | "high" | "emergency";
export type TranscriptRole = "ai" | "patient";
export type TranscriptSource = "system" | "typed" | "voice";

export type TranscriptTurn = {
  id: string;
  role: TranscriptRole;
  content: string;
  timestamp: string;
  source: TranscriptSource;
};

export type InterviewField = {
  label: string;
  value: string;
};

export type InterviewSessionState = {
  sessionId: string;
  createdAt: string;
  status: InterviewStatus;
  currentQuestion: string | null;
  transcript: TranscriptTurn[];
  extractedFields: InterviewField[];
  triageLevel: TriageLevel | null;
  routingHint: string;
  progress: number;
  reportReady: boolean;
};

export type IntakeReport = {
  reportId: string;
  sessionId: string;
  createdAt: string;
  chiefComplaint: string;
  riskLevel: TriageLevel;
  recommendedRouting: string;
  summary: string;
  notes: string;
  missingInformation: string[];
  extractedFields: InterviewField[];
  nextSteps: string[];
  transcript: TranscriptTurn[];
};

export type AppointmentSlot = {
  id: string;
  doctor: string;
  specialty: string;
  dateLabel: string;
  timeLabel: string;
  location: string;
  visitType: string;
  recommendation: string;
};

export type BookingConfirmation = {
  bookingId: string;
  slot: AppointmentSlot;
  message: string;
  instructions: string[];
};

type StoredSession = {
  sessionId: string;
  createdAt: string;
  status: InterviewStatus;
  questionIndex: number;
  transcript: TranscriptTurn[];
  answers: string[];
  extractedFields: InterviewField[];
  triageLevel: TriageLevel | null;
  routingHint: string;
};

type LiveSession = {
  sessionId: string;
  createdAt: string;
  status: InterviewStatus;
  transcript: TranscriptTurn[];
  totalQuestions: number;
  progress: number;
  triageLevel: TriageLevel | null;
  routingHint: string;
};

function delay(ms = 350) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isBrowser() {
  return typeof window !== "undefined";
}

function createId(prefix: string) {
  const generated =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2, 10);

  return `${prefix}-${generated}`;
}

function safeRead<T>(storageKey: string): T | null {
  if (!isBrowser()) {
    return null;
  }

  const rawValue = window.localStorage.getItem(storageKey);

  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as T;
  } catch {
    return null;
  }
}

function safeWrite(storageKey: string, value: unknown) {
  if (!isBrowser()) {
    return;
  }

  window.localStorage.setItem(storageKey, JSON.stringify(value));
}

function safeRemove(storageKey: string) {
  if (!isBrowser()) {
    return;
  }

  window.localStorage.removeItem(storageKey);
}

function makeTurn(
  role: TranscriptRole,
  content: string,
  source: TranscriptSource
): TranscriptTurn {
  return {
    id: createId(role),
    role,
    content,
    source,
    timestamp: new Date().toISOString(),
  };
}

function deriveFields(answers: string[]) {
  const labels = [
    "Chief complaint",
    "Symptom timeline",
    "Red-flag check",
    "Visit goal",
  ] as const;

  return answers
    .map((answer, index) => {
      if (!answer.trim()) {
        return null;
      }

      return {
        label: labels[index] ?? `Interview note ${index + 1}`,
        value: answer.trim(),
      };
    })
    .filter((field): field is InterviewField => field !== null);
}

function deriveRiskLevel(answers: string[]) {
  const joined = answers.join(" ").toLowerCase();

  if (
    /(can'?t breathe|cannot breathe|shortness of breath|chest pain|passed out|fainting|stroke|confused|unresponsive)/.test(
      joined
    )
  ) {
    return "emergency" as const;
  }

  if (
    /(trouble breathing|severe pain|severe bleeding|high fever|worsening rapidly|dehydration)/.test(
      joined
    )
  ) {
    return "high" as const;
  }

  if (/(fever|vomit|vomiting|dizziness|persistent|infection|rash)/.test(joined)) {
    return "moderate" as const;
  }

  return "low" as const;
}

function deriveRoutingHint(riskLevel: TriageLevel) {
  switch (riskLevel) {
    case "emergency":
      return "Escalate to emergency evaluation immediately.";
    case "high":
      return "Offer same-day urgent care or clinician callback.";
    case "moderate":
      return "Offer next-available primary care or telehealth intake.";
    default:
      return "Offer routine visit options and self-care follow-up guidance.";
  }
}

function sessionToState(session: StoredSession): InterviewSessionState {
  return {
    sessionId: session.sessionId,
    createdAt: session.createdAt,
    status: session.status,
    currentQuestion:
      session.status === "completed" ? null : DEMO_QUESTIONS[session.questionIndex] ?? null,
    transcript: session.transcript,
    extractedFields: session.extractedFields,
    triageLevel: session.triageLevel,
    routingHint: session.routingHint,
    progress: Math.min((session.answers.length / DEMO_QUESTIONS.length) * 100, 100),
    reportReady: session.status === "completed",
  };
}

function buildNewSession(): StoredSession {
  return {
    sessionId: createId("session"),
    createdAt: new Date().toISOString(),
    status: "in_progress",
    questionIndex: 0,
    answers: [],
    extractedFields: [],
    triageLevel: null,
    routingHint: "Start the intake to reveal the recommended routing path.",
    transcript: [makeTurn("ai", DEMO_QUESTIONS[0], "system")],
  };
}

function getStoredSession() {
  return safeRead<StoredSession>(SESSION_STORAGE_KEY);
}

function getStoredReport() {
  return safeRead<IntakeReport>(REPORT_STORAGE_KEY);
}

function getStoredBooking() {
  return safeRead<BookingConfirmation>(BOOKING_STORAGE_KEY);
}

function buildReport(session: StoredSession): IntakeReport {
  const chiefComplaint =
    session.answers[0]?.trim() || "Patient requested guided intake support.";
  const riskLevel = session.triageLevel ?? deriveRiskLevel(session.answers);
  const routingHint = deriveRoutingHint(riskLevel);
  const missingInformation = DEMO_QUESTIONS.filter((_, index) => !session.answers[index]).map(
    (_, index) => `Response needed for question ${index + 1}.`
  );

  return {
    reportId: createId("report"),
    sessionId: session.sessionId,
    createdAt: new Date().toISOString(),
    chiefComplaint,
    riskLevel,
    recommendedRouting: routingHint,
    summary: `Patient reports ${chiefComplaint.toLowerCase()} and completed ${session.answers.length} of ${DEMO_QUESTIONS.length} guided intake prompts. The current prototype recommends a ${routingHint.toLowerCase()}`,
    notes:
      session.answers[1]?.trim() ||
      "Timeline and symptom progression have not been fully documented yet.",
    missingInformation,
    extractedFields: session.extractedFields,
    nextSteps: [
      "Clinician reviews the intake summary and transcript.",
      "Scheduling module matches the patient to appropriate appointment slots.",
      "Patient receives a clear follow-up plan with escalation guidance.",
    ],
    transcript: session.transcript,
  };
}

type BackendSessionSummary = {
  session_id: string;
  form_id: string;
  status: string;
  answers: Record<string, unknown>;
  triage_level: TriageLevel | null;
  triage_flags: string[];
  scores: Record<string, number>;
  chief_complaint: string;
  recommended_routing: string;
  notes: string;
};

function summaryToReport(
  summary: BackendSessionSummary,
  transcript: TranscriptTurn[]
): IntakeReport {
  const riskLevel = summary.triage_level ?? "low";
  const extractedFields: InterviewField[] = Object.entries(summary.answers).map(
    ([label, value]) => ({ label, value: String(value ?? "") })
  );

  return {
    reportId: createId("report"),
    sessionId: summary.session_id,
    createdAt: new Date().toISOString(),
    chiefComplaint: summary.chief_complaint || "See transcript.",
    riskLevel,
    recommendedRouting: summary.recommended_routing || deriveRoutingHint(riskLevel),
    summary: `Form: ${summary.form_id}. ${summary.notes || ""}`.trim(),
    notes: summary.notes,
    missingInformation: [],
    extractedFields,
    nextSteps: [
      "Clinician reviews the intake summary and transcript.",
      "Scheduling module matches the patient to appropriate appointment slots.",
      "Patient receives a clear follow-up plan with escalation guidance.",
    ],
    transcript,
  };
}

function buildSlots(riskLevel: TriageLevel) {
  if (riskLevel === "emergency" || riskLevel === "high") {
    return [
      {
        id: "slot-urgent-1",
        doctor: "Dr. Rivera",
        specialty: "Urgent Care",
        dateLabel: "Today",
        timeLabel: "2:15 PM",
        location: "Downtown Immediate Care",
        visitType: "In-person",
        recommendation: "Fastest same-day slot for higher-risk symptoms.",
      },
      {
        id: "slot-urgent-2",
        doctor: "Dr. Okafor",
        specialty: "Acute Virtual Clinic",
        dateLabel: "Today",
        timeLabel: "4:00 PM",
        location: "Telehealth",
        visitType: "Video visit",
        recommendation: "Rapid clinician check-in if travel is difficult.",
      },
      {
        id: "slot-urgent-3",
        doctor: "Dr. Patel",
        specialty: "Primary Care",
        dateLabel: "Tomorrow",
        timeLabel: "8:30 AM",
        location: "South Loop Family Medicine",
        visitType: "In-person",
        recommendation: "Early next-day follow-up if symptoms remain stable.",
      },
    ] satisfies AppointmentSlot[];
  }

  return [
    {
      id: "slot-routine-1",
      doctor: "Dr. Nguyen",
      specialty: "Family Medicine",
      dateLabel: "Tomorrow",
      timeLabel: "10:30 AM",
      location: "River North Clinic",
      visitType: "In-person",
      recommendation: "Balanced option for a routine in-person workup.",
    },
    {
      id: "slot-routine-2",
      doctor: "Dr. Harris",
      specialty: "Telehealth Intake",
      dateLabel: "Tomorrow",
      timeLabel: "1:00 PM",
      location: "Telehealth",
      visitType: "Video visit",
      recommendation: "Fastest remote visit for low-to-moderate acuity symptoms.",
    },
    {
      id: "slot-routine-3",
      doctor: "Dr. Chen",
      specialty: "Internal Medicine",
      dateLabel: "Wednesday",
      timeLabel: "9:15 AM",
      location: "West Loop Internal Medicine",
      visitType: "In-person",
      recommendation: "Strong choice when labs or a physical exam may be helpful.",
    },
  ] satisfies AppointmentSlot[];
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export function getInterviewSession() {
  const session = getStoredSession();
  return session ? sessionToState(session) : null;
}

export async function resetInterview() {
  safeRemove(SESSION_STORAGE_KEY);
  safeRemove(LIVE_SESSION_KEY);
  safeRemove(REPORT_STORAGE_KEY);
  safeRemove(BOOKING_STORAGE_KEY);
  await delay(100);
}

export async function startInterview(formId = "hpi") {
  if (!isMockApiEnabled) {
    const response = await apiFetch<{
      session_id: string;
      form_title: string;
      first_question: string;
      total_questions: number;
    }>("/interview/start", {
      method: "POST",
      body: JSON.stringify({ form_id: formId }),
    });

    const firstQuestion = response.first_question;
    const liveSession: LiveSession = {
      sessionId: response.session_id,
      createdAt: new Date().toISOString(),
      status: "in_progress",
      transcript: [makeTurn("ai", firstQuestion, "system")],
      totalQuestions: response.total_questions,
      progress: 0,
      triageLevel: null,
      routingHint: "Intake in progress.",
    };
    safeWrite(LIVE_SESSION_KEY, liveSession);

    return {
      sessionId: liveSession.sessionId,
      createdAt: liveSession.createdAt,
      status: "in_progress" as const,
      currentQuestion: firstQuestion,
      transcript: liveSession.transcript,
      extractedFields: [],
      triageLevel: null,
      routingHint: liveSession.routingHint,
      progress: 0,
      reportReady: false,
    };
  }

  await delay();

  const existingSession = getStoredSession();

  if (existingSession) {
    return sessionToState(existingSession);
  }

  const createdSession = buildNewSession();
  safeWrite(SESSION_STORAGE_KEY, createdSession);
  return sessionToState(createdSession);
}

export async function sendInterviewAnswer(
  sessionId: string,
  answer: string,
  source: TranscriptSource = "typed"
) {
  if (!isMockApiEnabled) {
    const response = await apiFetch<{
      session_id: string;
      ai_response: string;
      question_answered_id: string;
      next_question_id: string | null;
      progress: number;
      triage_flag: boolean;
      triage_reason: string | null;
      form_complete: boolean;
    }>("/interview/respond", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, answer }),
    });

    const liveSession = safeRead<LiveSession>(LIVE_SESSION_KEY);
    const prevTranscript = liveSession?.transcript ?? [];
    const updatedTranscript = [
      ...prevTranscript,
      makeTurn("patient", answer, source),
    ];
    if (!response.form_complete) {
      updatedTranscript.push(makeTurn("ai", response.ai_response, "system"));
    }

    const progressPct = Math.round(response.progress * 100);
    const isComplete = response.form_complete;

    const updatedLive: LiveSession = {
      ...(liveSession ?? {
        sessionId,
        createdAt: new Date().toISOString(),
        totalQuestions: 0,
        routingHint: "",
      }),
      sessionId,
      status: isComplete ? "completed" : "in_progress",
      transcript: updatedTranscript,
      progress: progressPct,
      triageLevel: null,
      routingHint: liveSession?.routingHint ?? "",
    };
    safeWrite(LIVE_SESSION_KEY, updatedLive);

    return {
      sessionId,
      createdAt: updatedLive.createdAt,
      status: updatedLive.status,
      currentQuestion: isComplete ? null : response.ai_response,
      transcript: updatedTranscript,
      extractedFields: [],
      triageLevel: null,
      routingHint: updatedLive.routingHint,
      progress: progressPct,
      reportReady: isComplete,
    };
  }

  await delay();

  const session = getStoredSession();

  if (!session || session.sessionId !== sessionId) {
    throw new Error("Session not found. Start a new intake session.");
  }

  if (session.status === "completed") {
    return sessionToState(session);
  }

  const answerToStore = answer.trim();
  const updatedAnswers = [...session.answers, answerToStore];
  const triageLevel = deriveRiskLevel(updatedAnswers);
  const routingHint = deriveRoutingHint(triageLevel);
  const updatedTranscript = [
    ...session.transcript,
    makeTurn("patient", answerToStore, source),
  ];

  const isComplete = updatedAnswers.length >= DEMO_QUESTIONS.length;
  const nextQuestion = DEMO_QUESTIONS[updatedAnswers.length];

  if (nextQuestion) {
    updatedTranscript.push(makeTurn("ai", nextQuestion, "system"));
  }

  const nextSession: StoredSession = {
    ...session,
    questionIndex: Math.min(updatedAnswers.length, DEMO_QUESTIONS.length - 1),
    answers: updatedAnswers,
    transcript: updatedTranscript,
    extractedFields: deriveFields(updatedAnswers),
    triageLevel,
    routingHint,
    status: isComplete ? "completed" : "in_progress",
  };

  safeWrite(SESSION_STORAGE_KEY, nextSession);

  if (isComplete) {
    safeWrite(REPORT_STORAGE_KEY, buildReport(nextSession));
  }

  return sessionToState(nextSession);
}

export async function completeInterview(sessionId: string) {
  if (!isMockApiEnabled) {
    const summary = await apiFetch<BackendSessionSummary>(
      `/interview/${sessionId}/summary`
    );
    const liveSession = safeRead<LiveSession>(LIVE_SESSION_KEY);
    const transcript = liveSession?.transcript ?? [];
    const report = summaryToReport(summary, transcript);
    safeWrite(REPORT_STORAGE_KEY, report);

    const completedLive: LiveSession = {
      ...(liveSession ?? {
        sessionId,
        createdAt: new Date().toISOString(),
        totalQuestions: 0,
        routingHint: report.recommendedRouting,
      }),
      sessionId,
      status: "completed",
      triageLevel: summary.triage_level ?? null,
      routingHint: report.recommendedRouting,
    };
    safeWrite(LIVE_SESSION_KEY, completedLive);

    return {
      sessionId,
      createdAt: completedLive.createdAt,
      status: "completed" as const,
      currentQuestion: null,
      transcript,
      extractedFields: report.extractedFields,
      triageLevel: completedLive.triageLevel,
      routingHint: completedLive.routingHint,
      progress: 100,
      reportReady: true,
    };
  }

  await delay();

  const session = getStoredSession();

  if (!session || session.sessionId !== sessionId) {
    throw new Error("No active interview session was found.");
  }

  if (session.status === "completed") {
    return sessionToState(session);
  }

  const triageLevel = deriveRiskLevel(session.answers);
  const completedSession: StoredSession = {
    ...session,
    status: "completed",
    triageLevel,
    routingHint: deriveRoutingHint(triageLevel),
    extractedFields: deriveFields(session.answers),
  };

  safeWrite(SESSION_STORAGE_KEY, completedSession);
  safeWrite(REPORT_STORAGE_KEY, buildReport(completedSession));

  return sessionToState(completedSession);
}

export async function getReport(sessionId?: string) {
  if (!isMockApiEnabled) {
    // Use the report cached by completeInterview if it holds a real backend session id
    const cachedReport = getStoredReport();
    if (cachedReport && !cachedReport.sessionId.startsWith("session-")) {
      return cachedReport;
    }
    // Re-fetch using the live session id from localStorage (or the caller-supplied id)
    const liveSessionId = sessionId ?? safeRead<LiveSession>(LIVE_SESSION_KEY)?.sessionId;
    if (!liveSessionId) {
      throw new Error("No completed interview session found. Please complete an interview first.");
    }
    const summary = await apiFetch<BackendSessionSummary>(
      `/interview/${liveSessionId}/summary`
    );
    const liveSession = safeRead<LiveSession>(LIVE_SESSION_KEY);
    const transcript = liveSession?.transcript ?? [];
    const report = summaryToReport(summary, transcript);
    safeWrite(REPORT_STORAGE_KEY, report);
    return report;
  }

  await delay(250);

  const storedReport = getStoredReport();
  if (storedReport) {
    return storedReport;
  }

  // Mock mode with no completed session
  const existingSession = getStoredSession();
  if (existingSession?.status === "completed") {
    const completedReport = buildReport({
      ...existingSession,
      triageLevel: existingSession.triageLevel ?? deriveRiskLevel(existingSession.answers),
      routingHint:
        existingSession.routingHint ??
        deriveRoutingHint(existingSession.triageLevel ?? deriveRiskLevel(existingSession.answers)),
      extractedFields: deriveFields(existingSession.answers),
    });
    safeWrite(REPORT_STORAGE_KEY, completedReport);
    return completedReport;
  }

  throw new Error("No completed interview session found. Please complete an interview first.");
}

export async function getSchedulingSlots() {
  if (!isMockApiEnabled) {
    const response = await apiFetch<{ message?: string }>("/scheduling/slots");

    return [
      {
        id: createId("slot"),
        doctor: "Scheduling service",
        specialty: "Awaiting backend",
        dateLabel: "TBD",
        timeLabel: "TBD",
        location: "Pending data",
        visitType: "TBD",
        recommendation: response.message ?? "Connect real appointment slots here.",
      },
    ] satisfies AppointmentSlot[];
  }

  await delay(300);
  const report = await getReport();
  return buildSlots(report.riskLevel);
}

export async function bookAppointment(slotId: string) {
  if (!isMockApiEnabled) {
    const response = await apiFetch<{ message?: string }>("/scheduling/book", {
      method: "POST",
      body: JSON.stringify({ slot_id: slotId }),
    });

    return {
      bookingId: createId("booking"),
      slot: {
        id: slotId,
        doctor: "Assigned provider",
        specialty: "Scheduling service",
        dateLabel: "TBD",
        timeLabel: "TBD",
        location: "Pending",
        visitType: "Pending",
        recommendation: "Awaiting backend confirmation.",
      },
      message: response.message ?? "Booking created.",
      instructions: ["Sync the real confirmation payload into the frontend booking card."],
    };
  }

  await delay(350);
  const slots = await getSchedulingSlots();
  const selectedSlot = slots.find((slot) => slot.id === slotId);

  if (!selectedSlot) {
    throw new Error("The selected appointment slot is no longer available.");
  }

  const confirmation: BookingConfirmation = {
    bookingId: createId("booking"),
    slot: selectedSlot,
    message: `You are booked with ${selectedSlot.doctor} on ${selectedSlot.dateLabel} at ${selectedSlot.timeLabel}.`,
    instructions: [
      "Arrive 10 minutes early or join the video room 5 minutes before start time.",
      "Keep your symptom notes and medication list nearby for the clinician.",
      "Use urgent or emergency care sooner if symptoms worsen before the appointment.",
    ],
  };

  safeWrite(BOOKING_STORAGE_KEY, confirmation);
  return confirmation;
}

export async function getBookingConfirmation() {
  await delay(120);
  return getStoredBooking();
}

async function _triggerPdfDownload(url: string, filename: string): Promise<void> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`PDF download failed: ${res.status} ${res.statusText}`);
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}

export async function downloadFormPdf(sessionId: string): Promise<void> {
  await _triggerPdfDownload(
    `${BASE_URL}/report/${sessionId}/pdf`,
    `intake_form_${sessionId.slice(0, 8)}.pdf`,
  );
}

export async function downloadSummaryPdf(sessionId: string): Promise<void> {
  await _triggerPdfDownload(
    `${BASE_URL}/report/${sessionId}/summary-pdf`,
    `interview_summary_${sessionId.slice(0, 8)}.pdf`,
  );
}

export function printReport(report: IntakeReport) {
  if (!isBrowser()) {
    return;
  }

  const popup = window.open("", "_blank", "noopener,noreferrer,width=900,height=700");

  if (!popup) {
    return;
  }

  const fieldsMarkup = report.extractedFields
    .map((field) => `<li><strong>${field.label}:</strong> ${field.value}</li>`)
    .join("");
  const transcriptMarkup = report.transcript
    .map(
      (turn) =>
        `<li><strong>${turn.role === "ai" ? "PrelimMD" : "Patient"}:</strong> ${turn.content}</li>`
    )
    .join("");

  popup.document.write(`
    <html>
      <head>
        <title>PrelimMD Report</title>
        <style>
          body { font-family: Georgia, serif; margin: 40px; color: #132238; }
          h1, h2 { margin-bottom: 8px; }
          p, li { line-height: 1.6; }
          .pill { display: inline-block; padding: 6px 12px; border-radius: 999px; background: #e8efe8; }
        </style>
      </head>
      <body>
        <h1>PrelimMD Intake Summary</h1>
        <p class="pill">Risk level: ${report.riskLevel}</p>
        <h2>Chief Complaint</h2>
        <p>${report.chiefComplaint}</p>
        <h2>Routing</h2>
        <p>${report.recommendedRouting}</p>
        <h2>Summary</h2>
        <p>${report.summary}</p>
        <h2>Structured Fields</h2>
        <ul>${fieldsMarkup}</ul>
        <h2>Transcript</h2>
        <ul>${transcriptMarkup}</ul>
      </body>
    </html>
  `);
  popup.document.close();
  popup.focus();
  popup.print();
}
