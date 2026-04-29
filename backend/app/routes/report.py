from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.services import report_generator

router = APIRouter()


class GenerateReportRequest(BaseModel):
    session_id: str


@router.post("/generate")
async def generate_report(body: GenerateReportRequest):
    try:
        return await report_generator.generate(body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{session_id}")
async def get_report(session_id: str):
    report = report_generator.get_report(session_id)
    if report:
        return report
    try:
        return await report_generator.generate(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{session_id}/pdf")
async def download_report_pdf(session_id: str):
    report = report_generator.get_report(session_id)
    if not report:
        try:
            report = await report_generator.generate(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
    try:
        pdf_bytes = report_generator.to_pdf(report)
        short_id = session_id[:8]
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="prelimmd-{short_id}.pdf"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")
