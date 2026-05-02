# app/routes/report.py
# Clinical brief / intake report routes.
# Owner: Person 2 generates the brief; report teammate owns PDF rendering.

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.services import ai_engine, report_generator

router = APIRouter()


@router.get("/{form_id}")
def get_report(form_id: str):
    """
    Return the clinical brief for a completed form in the IntakeReport shape
    the frontend ReportViewer expects.
    """
    brief = ai_engine.get_clinical_brief(form_id)
    if not brief:
        raise HTTPException(
            status_code=404,
            detail=f"No clinical brief found for form_id={form_id}. "
                   "Run POST /forms/{form_id}/submit first.",
        )

    # Shape matches frontend IntakeReport type exactly
    return {
        "reportId":            brief.report_id,
        "sessionId":           brief.form_id,
        "createdAt":           brief.created_at,
        "chiefComplaint":      brief.chief_complaint,
        "riskLevel":           brief.risk_level,
        "recommendedRouting":  brief.recommended_routing,
        "summary":             brief.summary,
        "notes":               brief.notes,
        "missingInformation":  brief.missing_information,
        "extractedFields":     brief.extracted_fields,
        "transcript":          [t.model_dump() for t in brief.transcript],
    }


@router.get("/{form_id}/pdf")
def download_report_pdf(form_id: str):
    """Return the clinical brief as a downloadable PDF."""
    brief = ai_engine.get_clinical_brief(form_id)
    if not brief:
        raise HTTPException(
            status_code=404,
            detail=f"No clinical brief found for form_id={form_id}. "
                   "Run POST /forms/{form_id}/submit first.",
        )
    pdf_bytes = report_generator.to_pdf(brief)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=clinical_brief_{form_id[:8]}.pdf"},
    )


@router.post("/generate")
def generate_report():
    # Legacy placeholder — brief is now auto-generated on POST /forms/{id}/submit
    return {"message": "Clinical brief is generated automatically on form submit."}
