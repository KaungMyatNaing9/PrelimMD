# app/routes/forms.py
# Form upload, parsing, prefill, and submission routes.
# Owner: AI (Person 2)

import pymupdf4llm
import pymupdf
from fastapi import APIRouter, HTTPException, UploadFile

from app.models.schemas import CallResponses, CompletedForm, FormSchema, PrefilledForm
from app.services import ai_engine

router = APIRouter()


def _extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from a PDF using pymupdf4llm, or decode as plain text.

    Raises ValueError for image-only (scanned) PDFs that contain no embedded text,
    since we have no OCR backend — better to fail loudly than return garbage.
    """
    if filename.lower().endswith(".pdf"):
        doc = pymupdf.Document(stream=file_bytes, filetype="pdf")
        text = pymupdf4llm.to_markdown(doc)
        if not text.strip():
            raise ValueError(
                "PDF appears to be a scanned image with no embedded text. "
                "Please upload a text-based PDF or a plain-text (.txt) form."
            )
        return text
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
        return ai_engine.retrieve_and_diff(schema, patient_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Retrieval agent failed: {exc}")


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
