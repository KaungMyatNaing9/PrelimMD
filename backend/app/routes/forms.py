# app/routes/forms.py
# Form upload, parsing, prefill, and submission routes.
# Owner: AI (Person 2)

import base64
import pymupdf4llm
import pymupdf
from fastapi import APIRouter, HTTPException, UploadFile
from openai import OpenAI

from app.config import settings
from app.models.schemas import CallResponses, CompletedForm, FormSchema, PrefilledForm
from app.services import ai_engine

router = APIRouter()


def _ocr_pdf(doc: pymupdf.Document) -> str:
    """OCR fallback: render pages to PNG and send to gpt-4o vision. No extra deps."""
    content: list = [{"type": "text", "text": (
        "These are pages from a scanned medical intake form. "
        "Extract ALL text exactly as it appears — preserve labels, field names, "
        "checkboxes, and any pre-filled values. Output plain text only."
    )}]
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_b64 = base64.b64encode(pix.tobytes("png")).decode()
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"},
        })
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def _extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Extract text from a PDF or plain-text file.
    Digital PDFs: pymupdf4llm (fast, structure-preserving).
    Scanned/image PDFs: automatic fallback to gpt-4o vision OCR.
    """
    if filename.lower().endswith(".pdf"):
        doc = pymupdf.Document(stream=file_bytes, filetype="pdf")
        text = pymupdf4llm.to_markdown(doc)
        if text.strip():
            return text
        return _ocr_pdf(doc)
    return file_bytes.decode("utf-8", errors="ignore")


@router.post("/upload", response_model=FormSchema)
async def upload_form(file: UploadFile):
    """
    Upload a PDF or text form. Parses it into a structured FormSchema via LLM.
    Returns the schema with a generated form_id — use this ID for all follow-up calls.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        ocr_text = _extract_text(content, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not extract text: {exc}")

    if not ocr_text.strip():
        raise HTTPException(status_code=422, detail="No text found in the uploaded file.")

    try:
        return ai_engine.parse_form(ocr_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Form parsing failed: {exc}")


@router.get("/{form_id}/schema", response_model=FormSchema)
def get_schema(form_id: str):
    """Return the parsed schema for a previously uploaded form."""
    schema = ai_engine.get_form_schema(form_id)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Form {form_id} not found.")
    return schema


@router.post("/{form_id}/prefill", response_model=PrefilledForm)
def prefill_form(form_id: str, patient_id: str):
    """
    Run the data retrieval agent — diff the form schema against the patient's EHR.
    Returns filled fields (from records) and missing fields (as questions for Person 3).
    """
    schema = ai_engine.get_form_schema(form_id)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Form {form_id} not found.")
    try:
        return ai_engine.prefill_from_db(schema, patient_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Prefill failed: {exc}")


@router.post("/{form_id}/submit", response_model=CompletedForm)
def submit_form(form_id: str, responses: CallResponses):
    """
    Run the form filler agent — parse call responses and merge with EHR data.
    Returns the completed form ready for the nurse portal.
    """
    try:
        return ai_engine.finalize_form(form_id, responses)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Form filler failed: {exc}")


@router.get("/{form_id}/completed", response_model=CompletedForm)
def get_completed_form(form_id: str):
    """
    Retrieve the completed form after submit has been called.
    Report/nurse portal teammates call this to get the finalized data.
    """
    completed = ai_engine.get_completed_form(form_id)
    if not completed:
        raise HTTPException(status_code=404, detail=f"No completed form found for {form_id}. Run POST /{form_id}/submit first.")
    return completed
