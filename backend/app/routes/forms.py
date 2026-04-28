# app/routes/forms.py
# Routes for parsing clinical PDFs into FormSchema JSON.
# The /parse/upload endpoint also registers the parsed form in-memory so it
# can be used immediately by the interview engine without writing to disk.

import re
import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.services import ai_engine, form_parser

router = APIRouter()


def _slug_from_filename(filename: str) -> str:
    """Derive a safe form_id slug from an uploaded filename."""
    stem = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    short_id = uuid.uuid4().hex[:8]
    return f"upload_{slug}_{short_id}" if slug else f"upload_{short_id}"


def _title_from_filename(filename: str) -> str:
    stem = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    return re.sub(r"[-_]+", " ", stem).strip().title() or "Uploaded Form"


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
    form_id: str = "",
    title: str = "",
    description: str = "",
):
    """
    Accept a PDF file upload and run the 5-stage extraction pipeline.
    form_id and title are optional — both are derived from the filename when omitted.
    The parsed form is registered in-memory so /interview/start can use it immediately.
    Returns the parsed FormSchema and a ParseReport.
    """
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(
            status_code=415,
            detail="Only PDF files are accepted (application/pdf).",
        )

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = file.filename or "form.pdf"
    resolved_form_id = form_id.strip() or _slug_from_filename(filename)
    resolved_title = title.strip() or _title_from_filename(filename)

    try:
        form, report = await form_parser.parse_pdf(
            pdf_source=pdf_bytes,
            form_id=resolved_form_id,
            title=resolved_title,
            description=description,
            source_url=filename,
        )
        total_questions = sum(len(s.questions) for s in form.sections)
        if total_questions == 0:
            raise HTTPException(
                status_code=422,
                detail="PDF parsing produced no questions. Check that the file is a clinical intake form.",
            )
        ai_engine.register_form(form)
        return {"form": form.model_dump(), "report": report.model_dump()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PDF parse failed: {exc}")
