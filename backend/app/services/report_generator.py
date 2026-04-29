import io
import uuid
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services import ai_engine

_reports: dict[str, dict] = {}

_RISK_COLORS = {
    "low": colors.HexColor("#16a34a"),
    "moderate": colors.HexColor("#d97706"),
    "high": colors.HexColor("#ea580c"),
    "emergency": colors.HexColor("#dc2626"),
}


async def generate(session_id: str) -> dict:
    summary = await ai_engine.get_summary(session_id)

    report = {
        "report_id": f"report-{uuid.uuid4()}",
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chief_complaint": summary.get("chief_complaint") or "Not captured",
        "risk_level": summary.get("triage_level", "low"),
        "recommended_routing": summary.get("routing_hint") or "General Medicine evaluation",
        "summary": summary.get("summary_text") or "",
        "notes": _build_notes(summary),
        "missing_information": _find_missing(summary),
        "extracted_fields": summary.get("extracted_fields", []),
        "next_steps": _build_next_steps(summary),
        "transcript": summary.get("transcript", []),
    }

    _reports[session_id] = report
    return report


def get_report(session_id: str) -> dict | None:
    return _reports.get(session_id)


def to_pdf(report: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    brand_blue = colors.HexColor("#1a3a5c")
    light_gray = colors.HexColor("#f3f4f6")
    mid_gray = colors.HexColor("#6b7280")
    dark_text = colors.HexColor("#1f2937")

    title_style = ParagraphStyle("PTitle", parent=styles["Normal"], fontSize=22,
                                  textColor=brand_blue, alignment=TA_CENTER,
                                  fontName="Helvetica-Bold", spaceAfter=2)
    subtitle_style = ParagraphStyle("PSub", parent=styles["Normal"], fontSize=11,
                                     textColor=mid_gray, alignment=TA_CENTER, spaceAfter=18)
    section_style = ParagraphStyle("PSection", parent=styles["Normal"], fontSize=11,
                                    textColor=brand_blue, fontName="Helvetica-Bold",
                                    spaceBefore=14, spaceAfter=6)
    body_style = ParagraphStyle("PBody", parent=styles["Normal"], fontSize=9,
                                 textColor=dark_text, leading=15, spaceAfter=3)
    small_style = ParagraphStyle("PSmall", parent=styles["Normal"], fontSize=7,
                                  textColor=mid_gray, alignment=TA_CENTER, spaceAfter=2)

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("PrelimMD", title_style))
    story.append(Paragraph("Pre-Visit Intake Summary — Confidential", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=brand_blue, spaceAfter=10))

    # ── Meta table ────────────────────────────────────────────────────────────
    risk_level = report.get("risk_level", "low")
    risk_color = _RISK_COLORS.get(risk_level, colors.HexColor("#16a34a"))
    created = report.get("created_at", "")[:19].replace("T", " ") + " UTC"

    meta = [
        ["Report ID", report.get("report_id", "")[:28]],
        ["Session", report.get("session_id", "")[:28]],
        ["Generated", created],
        ["Risk Level", risk_level.upper()],
    ]
    meta_table = Table(meta, colWidths=[1.4 * inch, 5.1 * inch])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (0, -1), mid_gray),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 3), (1, 3), risk_color),
        ("FONTNAME", (1, 3), (1, 3), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(meta_table)
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb"),
                             spaceBefore=10, spaceAfter=4))

    # ── Chief complaint & routing ─────────────────────────────────────────────
    story.append(Paragraph("Chief Complaint", section_style))
    story.append(Paragraph(report.get("chief_complaint", "Not captured"), body_style))

    story.append(Paragraph("Recommended Routing", section_style))
    story.append(Paragraph(report.get("recommended_routing", "General Medicine evaluation"), body_style))

    # ── Clinical summary ──────────────────────────────────────────────────────
    summary_text = report.get("summary", "")
    if summary_text:
        story.append(Paragraph("Clinical Summary", section_style))
        for line in summary_text.split("\n"):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 4))
                continue
            # Section headings in the summary are ALL CAPS or end with colon
            if line.isupper() or (line.endswith(":") and len(line) < 40):
                story.append(Paragraph(f"<b>{line}</b>", body_style))
            elif line.startswith("[URGENT]"):
                urgent_style = ParagraphStyle(
                    "Urgent", parent=body_style, textColor=colors.HexColor("#dc2626"),
                    fontName="Helvetica-Bold"
                )
                story.append(Paragraph(line, urgent_style))
            else:
                story.append(Paragraph(line, body_style))

    # ── Structured fields table ───────────────────────────────────────────────
    fields = report.get("extracted_fields", [])
    if fields:
        story.append(Paragraph("Structured Intake Data", section_style))
        table_data = [["Field", "Value"]] + [[f["label"], f["value"]] for f in fields]
        col_widths = [2.0 * inch, 4.5 * inch]
        field_table = Table(table_data, colWidths=col_widths)
        field_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_blue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 1), (0, -1), mid_gray),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [light_gray, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(field_table)

    # ── Notes & missing info ──────────────────────────────────────────────────
    if report.get("notes"):
        story.append(Paragraph("Additional Notes", section_style))
        story.append(Paragraph(report["notes"], body_style))

    missing = report.get("missing_information", [])
    if missing:
        story.append(Paragraph("Information Gaps", section_style))
        for item in missing:
            story.append(Paragraph(f"• {item}", body_style))

    # ── Next steps ────────────────────────────────────────────────────────────
    next_steps = report.get("next_steps", [])
    if next_steps:
        story.append(Paragraph("Recommended Next Steps", section_style))
        for i, step in enumerate(next_steps, 1):
            story.append(Paragraph(f"{i}. {step}", body_style))

    # ── Transcript ────────────────────────────────────────────────────────────
    transcript = report.get("transcript", [])
    if transcript:
        story.append(Spacer(1, 14))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
        story.append(Paragraph("Interview Transcript", section_style))
        for turn in transcript:
            is_ai = turn.get("role") == "ai"
            speaker = "Maya (Nurse)" if is_ai else "Patient"
            color_hex = "#1a3a5c" if is_ai else "#374151"
            text = f'<font color="{color_hex}"><b>{speaker}:</b></font> {turn.get("content", "")}'
            story.append(Paragraph(text, body_style))
            story.append(Spacer(1, 3))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
    story.append(Paragraph(
        "This document is an AI-assisted pre-visit intake summary intended for clinical review only. "
        "It does not constitute a medical diagnosis. All clinical information must be verified by a "
        "qualified healthcare professional before acting on it.",
        small_style,
    ))
    story.append(Paragraph(
        "Generated by PrelimMD · Confidential Patient Information",
        small_style,
    ))

    doc.build(story)
    return buffer.getvalue()


def _build_notes(summary: dict) -> str:
    parts = []
    if summary.get("symptom_onset"):
        parts.append(f"Onset: {summary['symptom_onset']}")
    if summary.get("severity_score") is not None:
        parts.append(f"Severity: {summary['severity_score']}/10")
    if summary.get("is_worsening") is True:
        parts.append("Symptoms worsening")
    if summary.get("existing_conditions"):
        parts.append(f"Conditions: {', '.join(summary['existing_conditions'])}")
    if summary.get("medications"):
        parts.append(f"Medications: {', '.join(summary['medications'])}")
    return " | ".join(parts) if parts else "No additional notes."


def _find_missing(summary: dict) -> list[str]:
    missing = []
    if not summary.get("symptom_onset"):
        missing.append("Symptom onset timeline not fully captured")
    if summary.get("severity_score") is None:
        missing.append("Severity rating not provided")
    if not summary.get("allergies"):
        missing.append("Allergy history not confirmed")
    if not summary.get("medications"):
        missing.append("Medication list not confirmed")
    return missing


def _build_next_steps(summary: dict) -> list[str]:
    triage = summary.get("triage_level", "low")
    dept = summary.get("suggested_department") or "General Medicine"
    steps = []

    if triage == "emergency":
        steps.append("[URGENT] Escalate to emergency evaluation immediately.")
        steps.append("Notify clinical team — do not delay.")
    elif triage == "high":
        steps.append(f"Offer same-day appointment with {dept} or urgent care.")
        steps.append("Clinical team to call patient and confirm they can safely wait.")
    elif triage == "moderate":
        steps.append(f"Schedule appointment with {dept} within 24–48 hours.")
        steps.append("Provide patient with symptom monitoring guidance.")
    else:
        steps.append(f"Schedule routine appointment with {dept}.")
        steps.append("Confirm patient has self-care guidance while awaiting appointment.")

    steps.append("Clinician reviews intake summary and transcript before appointment.")
    steps.append("Patient receives confirmation with pre-appointment instructions.")
    return steps
