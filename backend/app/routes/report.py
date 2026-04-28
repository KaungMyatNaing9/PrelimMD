# app/routes/report.py
# HTTP routes for generating and retrieving intake reports.

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.services import ai_engine, report_generator

router = APIRouter()


@router.post("/generate")
def generate_report():
    return {"message": "placeholder — report generation not yet implemented"}


@router.get("/{session_id}/pdf", summary="Download filled intake form as PDF")
async def download_form_pdf(session_id: str):
    """
    Return the clinical intake form with the patient's answers filled in as a
    downloadable PDF.
    """
    try:
        summary = await ai_engine.get_summary(session_id)
        form = ai_engine.load_form(summary.form_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to retrieve session: {exc}")

    try:
        pdf_bytes = report_generator.generate_form_pdf(summary, form)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    filename = f"intake_form_{session_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}/summary-pdf", summary="Download interview summary as PDF")
async def download_summary_pdf(session_id: str):
    """
    Return a narrative summary of the interview — chief complaint, triage,
    routing, and full transcript — as a downloadable PDF.
    """
    try:
        summary = await ai_engine.get_summary(session_id)
        transcript = ai_engine.get_transcript(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to retrieve session: {exc}")

    try:
        pdf_bytes = report_generator.generate_summary_pdf(summary, transcript)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    filename = f"interview_summary_{session_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}", summary="Get structured report JSON")
async def get_report(session_id: str):
    # TODO: Report - retrieve and return structured report JSON
    return {"session_id": session_id, "message": "placeholder — report retrieval not yet implemented"}
