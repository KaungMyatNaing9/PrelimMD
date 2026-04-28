# app/models/schemas.py
# Pydantic request/response models shared across all routes.

from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str


# ── Voice ─────────────────────────────────────────────────────────────────────

class TranscribeResponse(BaseModel):
    success: bool
    transcript: str
    confidence: Optional[float] = None   # 0.0–1.0, if returned by Deepgram
    language: Optional[str] = None       # detected language code, e.g. "en"
    duration: Optional[float] = None     # audio duration in seconds
    raw: Optional[Any] = None            # full Deepgram response for downstream use


# ── Form schema (used by form_parser and ai_engine) ───────────────────────────

QuestionType = Literal[
    "free_text",
    "yes_no",
    "single_choice",
    "multi_choice",
    "scale",
    "numeric",
]


class QuestionOption(BaseModel):
    value: Union[int, float, str]
    label: str


class SkipCondition(BaseModel):
    question_id: str
    condition: Literal["equals", "not_equals", "greater_than", "less_than"]
    value: Union[str, int, float, bool]


class QuestionSchema(BaseModel):
    id: str
    text: str
    conversational_hint: str = ""
    type: QuestionType
    required: bool = True
    options: list[QuestionOption] = Field(default_factory=list)
    scoring_weight: int = 1
    skip_if: Optional[SkipCondition] = None


class SectionSchema(BaseModel):
    id: str
    title: str
    instructions: str = ""
    questions: list[QuestionSchema]


class ScoringRange(BaseModel):
    min: int
    max: int
    triage_level: Literal["low", "moderate", "high", "emergency"]
    label: str


class ScoringSchema(BaseModel):
    enabled: bool = False
    method: Literal["sum", "weighted"] = "sum"
    ranges: list[ScoringRange] = Field(default_factory=list)


class FormSchema(BaseModel):
    form_id: str
    title: str
    description: str = ""
    source_url: str = ""
    version: str = "1.0"
    sections: list[SectionSchema]
    scoring: ScoringSchema = Field(default_factory=ScoringSchema)


# ── Form parser ───────────────────────────────────────────────────────────────

class SectionBoundary(BaseModel):
    id: str
    title: str
    start_char: int
    end_char: int


class ParsedSectionQuestions(BaseModel):
    section_id: str
    questions: list[QuestionSchema]


class ParseReport(BaseModel):
    form_id: str
    sections_found: int
    sections_succeeded: list[str]
    sections_retried: list[str]
    sections_failed: list[str]
    questions_total: int
    questions_missing_hints: list[str]
    ambiguous_type_questions: list[str]
    scoring_extracted: bool
    warnings: list[str] = Field(default_factory=list)


# ── Interview session (ai_engine) ─────────────────────────────────────────────

TriageLevel = Literal["low", "moderate", "high", "emergency"]


class InterviewTurn(BaseModel):
    """Structured output the LLM returns for each patient response."""
    ai_response: str
    question_answered_id: str
    extracted_value: Any
    next_question_id: Optional[str]
    triage_flag: bool
    triage_reason: Optional[str]
    form_complete: bool


class TranscriptMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class SessionSummary(BaseModel):
    session_id: str
    form_id: str
    status: Literal["in_progress", "completed", "abandoned"]
    answers: dict[str, Any]
    triage_level: Optional[TriageLevel]
    triage_flags: list[str]
    scores: dict[str, int]
    chief_complaint: str = ""
    recommended_routing: str = ""
    notes: str = ""


# ── Interview HTTP request/response models ────────────────────────────────────

class InterviewStartRequest(BaseModel):
    form_id: str = "general_intake"


class InterviewStartResponse(BaseModel):
    session_id: str
    form_title: str
    first_question: str
    total_questions: int


class InterviewRespondRequest(BaseModel):
    session_id: str
    answer: str


class InterviewRespondResponse(BaseModel):
    session_id: str
    ai_response: str
    question_answered_id: str
    next_question_id: Optional[str]
    progress: float          # 0.0–1.0
    triage_flag: bool
    triage_reason: Optional[str]
    form_complete: bool
