const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const isMockApiEnabled = process.env.NEXT_PUBLIC_USE_MOCK_API !== "false";

const SESSION_STORAGE_KEY = "prelimmd-demo-session";
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
  safeRemove(REPORT_STORAGE_KEY);
  safeRemove(BOOKING_STORAGE_KEY);
  await delay(100);
}

export async function startInterview() {
  if (!isMockApiEnabled) {
    const response = await apiFetch<{ message?: string; session_id?: string }>(
      "/interview/start",
      { method: "POST" }
    );
    const firstQuestion = response.message ?? DEMO_QUESTIONS[0];

    return {
      sessionId: response.session_id ?? createId("session"),
      createdAt: new Date().toISOString(),
      status: "in_progress" as const,
      currentQuestion: firstQuestion,
      transcript: [makeTurn("ai", firstQuestion, "system")],
      extractedFields: [],
      triageLevel: null,
      routingHint: "Waiting on AI interview engine response.",
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
    const response = await apiFetch<{ message?: string }>(
      "/interview/respond",
      {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, answer }),
      }
    );

    return {
      sessionId,
      createdAt: new Date().toISOString(),
      status: "in_progress" as const,
      currentQuestion: response.message ?? "Awaiting backend interview contract.",
      transcript: [
        makeTurn("patient", answer, source),
        makeTurn("ai", response.message ?? "Awaiting backend interview contract.", "system"),
      ],
      extractedFields: [],
      triageLevel: null,
      routingHint: "Backend interview engine will drive routing once connected.",
      progress: 25,
      reportReady: false,
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
  if (!isMockApiEnabled && sessionId) {
    const response = await apiFetch<{ session_id?: string; message?: string }>(
      `/report/${sessionId}`
    );

    return {
      reportId: createId("report"),
      sessionId: response.session_id ?? sessionId,
      createdAt: new Date().toISOString(),
      chiefComplaint: "Backend report payload pending",
      riskLevel: "moderate" as const,
      recommendedRouting: response.message ?? "Awaiting report service contract.",
      summary: "Hook this screen to the shared report payload once backend models are finalized.",
      notes: "The frontend is ready to consume structured JSON here.",
      missingInformation: [],
      extractedFields: [],
      nextSteps: ["Finalize report schema and PDF endpoint contract."],
      transcript: [],
    };
  }

  await delay(250);

  const storedReport = getStoredReport();

  if (storedReport) {
    return storedReport;
  }

  const seededAnswers = [
    "Persistent sore throat with low fever.",
    "Symptoms began three days ago and feel slightly worse this morning.",
    "No chest pain, fainting, or trouble breathing reported.",
    "Patient wants guidance on whether same-day care is needed.",
  ];
  const existingSession = getStoredSession();
  const fallbackSession: StoredSession =
    existingSession ??
    {
      sessionId: createId("session"),
      createdAt: new Date().toISOString(),
      status: "completed",
      questionIndex: DEMO_QUESTIONS.length - 1,
      answers: seededAnswers,
      extractedFields: deriveFields(seededAnswers),
      triageLevel: "moderate",
      routingHint: deriveRoutingHint("moderate"),
      transcript: [
        makeTurn("ai", DEMO_QUESTIONS[0], "system"),
        makeTurn("patient", seededAnswers[0], "typed"),
        makeTurn("ai", DEMO_QUESTIONS[1], "system"),
        makeTurn("patient", seededAnswers[1], "typed"),
        makeTurn("ai", DEMO_QUESTIONS[2], "system"),
        makeTurn("patient", seededAnswers[2], "typed"),
        makeTurn("ai", DEMO_QUESTIONS[3], "system"),
        makeTurn("patient", seededAnswers[3], "typed"),
      ],
    };

  if (!existingSession) {
    safeWrite(SESSION_STORAGE_KEY, fallbackSession);
  }

  const fallbackReport = buildReport({
    ...fallbackSession,
    status: "completed",
    triageLevel:
      fallbackSession.triageLevel ?? deriveRiskLevel(fallbackSession.answers),
    routingHint:
      fallbackSession.routingHint ??
      deriveRoutingHint(fallbackSession.triageLevel ?? deriveRiskLevel(fallbackSession.answers)),
    extractedFields: deriveFields(fallbackSession.answers),
  });

  safeWrite(REPORT_STORAGE_KEY, fallbackReport);
  return fallbackReport;
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
