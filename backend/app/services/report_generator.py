# app/services/report_generator.py
# Generates branded PDF exports from completed interview sessions.
#
# Two output types:
#   generate_form_pdf   — the intake form with patient answers filled in
#   generate_summary_pdf — narrative summary: chief complaint, triage, transcript

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.models.schemas import FormSchema, SessionSummary, TranscriptMessage

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _now_label() -> str:
    return datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")


def generate_form_pdf(summary: SessionSummary, form: FormSchema) -> bytes:
    """Render a branded filled-form PDF from a session summary."""
    tmpl = _env.get_template("form_filled.html")
    html_str = tmpl.render(
        form=form,
        answers=summary.answers,
        meta=summary,
        generated_at=_now_label(),
    )
    return HTML(string=html_str).write_pdf()


def generate_summary_pdf(
    summary: SessionSummary,
    transcript: list[TranscriptMessage],
) -> bytes:
    """Render a branded conversation summary PDF from a session summary + transcript."""
    tmpl = _env.get_template("summary.html")
    visible = [m for m in transcript if m.role != "system"]
    html_str = tmpl.render(
        summary=summary,
        transcript=visible,
        generated_at=_now_label(),
    )
    return HTML(string=html_str).write_pdf()


def generate(session_summary: dict) -> dict:
    """Produce a structured intake report from a completed session summary."""
    raise NotImplementedError


def to_pdf(report: dict) -> bytes:
    """Render a structured report as a PDF and return raw bytes."""
    raise NotImplementedError
