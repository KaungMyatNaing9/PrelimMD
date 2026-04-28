# app/routes/forms.py
# Developer-time route for parsing clinical PDFs into FormSchema JSON.
# Not needed by the patient-facing interview flow — forms are pre-converted
# and committed to backend/app/forms/.

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.services import form_parser

router = APIRouter()


class ParsePdfUrlRequest(BaseModel):
    url: str
    form_id: str
    title: str
    description: str = ""


@router.post("/parse/url", summary="Parse a clinical PDF from a URL into a form JSON")
async def parse_pdf_from_url(body: ParsePdfUrlRequest):
    """
    Download a PDF from the given URL and run the 5-stage extraction pipeline.
    Returns the parsed FormSchema and a ParseReport for developer review.
    """
    try:
        form, report = await form_parser.parse_pdf(
            pdf_source=body.url,
            form_id=body.form_id,
            title=body.title,
            description=body.description,
            source_url=body.url,
        )
        return {"form": form.model_dump(), "report": report.model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PDF parse failed: {exc}")


@router.post("/parse/upload", summary="Parse an uploaded clinical PDF into a form JSON")
async def parse_pdf_upload(
    file: UploadFile,
    form_id: str,
    title: str,
    description: str = "",
):
    """
    Accept a PDF file upload and run the 5-stage extraction pipeline.
    Returns the parsed FormSchema and a ParseReport for developer review.
    """
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(
            status_code=415,
            detail="Only PDF files are accepted (application/pdf).",
        )

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        form, report = await form_parser.parse_pdf(
            pdf_source=pdf_bytes,
            form_id=form_id,
            title=title,
            description=description,
            source_url=file.filename or "",
        )
        return {"form": form.model_dump(), "report": report.model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PDF parse failed: {exc}")
