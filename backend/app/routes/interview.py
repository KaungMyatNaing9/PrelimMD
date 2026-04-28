# app/routes/interview.py
# HTTP routes for the LLM-driven clinical interview session.

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    InterviewRespondRequest,
    InterviewRespondResponse,
    InterviewStartRequest,
    InterviewStartResponse,
    SessionSummary,
)
from app.services import ai_engine

router = APIRouter()


@router.get("/forms", summary="List available interview forms")
def list_forms():
    """Return the form_id, title, and description for every available form."""
    return ai_engine.list_forms()


@router.post("/start", response_model=InterviewStartResponse, summary="Start an interview session")
async def start_interview(body: InterviewStartRequest):
    """
    Create a new interview session for the requested form and return the first question.
    """
    try:
        session_id, first_question, total = await ai_engine.start_session(body.form_id)
        form = ai_engine.load_form(body.form_id)
        return InterviewStartResponse(
            session_id=session_id,
            form_title=form.title,
            first_question=first_question,
            total_questions=total,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to start session: {exc}")


@router.post("/respond", response_model=InterviewRespondResponse, summary="Submit a patient answer")
async def respond_to_interview(body: InterviewRespondRequest):
    """
    Accept the patient's answer for the current question and return the AI's next response.
    """
    try:
        turn = await ai_engine.process_response(body.session_id, body.answer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Interview engine error: {exc}")

    # Compute progress for the response
    state = ai_engine._SESSIONS.get(body.session_id)
    progress = state.progress if state else 0.0

    return InterviewRespondResponse(
        session_id=body.session_id,
        ai_response=turn.ai_response,
        question_answered_id=turn.question_answered_id,
        next_question_id=turn.next_question_id,
        progress=progress,
        triage_flag=turn.triage_flag,
        triage_reason=turn.triage_reason,
        form_complete=turn.form_complete,
    )


@router.get("/{session_id}/summary", response_model=SessionSummary, summary="Get session summary")
async def get_interview_summary(session_id: str):
    """
    Return the structured triage summary for a session.
    Available any time — does not require the session to be complete.
    """
    try:
        return await ai_engine.get_summary(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Summary error: {exc}")
