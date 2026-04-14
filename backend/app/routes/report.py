# app/routes/report.py
# HTTP routes for generating and retrieving intake reports.
# Owner: Report teammate
#
# TODO: Report - GET  /{session_id}      → return structured JSON report
# TODO: Report - GET  /{session_id}/pdf  → return PDF file download
# TODO: Report - POST /generate          → trigger report generation for a completed session

from fastapi import APIRouter

router = APIRouter()


@router.post("/generate")
def generate_report():
    # TODO: Report - call report_generator.generate() with session data
    return {"message": "placeholder — report generation not yet implemented"}


@router.get("/{session_id}")
def get_report(session_id: str):
    # TODO: Report - retrieve and return structured report JSON
    return {"session_id": session_id, "message": "placeholder — report retrieval not yet implemented"}


@router.get("/{session_id}/pdf")
def download_report_pdf(session_id: str):
    # TODO: Report - stream PDF bytes with appropriate Content-Disposition header
    return {"session_id": session_id, "message": "placeholder — PDF download not yet implemented"}
