# app/routes/interview.py
# HTTP routes for the AI interview session.
# Owner: AI teammate
#
# TODO: AI - POST /start   → create a new session, return first question
# TODO: AI - POST /respond → accept patient answer, return next question or triage result
# TODO: AI - GET  /{session_id}/summary → return structured triage summary

from fastapi import APIRouter

router = APIRouter()


@router.post("/start")
def start_interview():
    # TODO: AI - call ai_engine.start_session() and return opening question
    return {"message": "placeholder — interview start not yet implemented"}


@router.post("/respond")
def respond_to_interview():
    # TODO: AI - call ai_engine.process_response() with patient input
    return {"message": "placeholder — interview respond not yet implemented"}


@router.get("/{session_id}/summary")
def get_interview_summary(session_id: str):
    # TODO: AI - retrieve and return structured session summary
    return {"session_id": session_id, "message": "placeholder — summary not yet implemented"}
