import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import ai_engine

router = APIRouter()


class StartRequest(BaseModel):
    session_id: str | None = None


class RespondRequest(BaseModel):
    session_id: str
    answer: str


@router.post("/start")
async def start_interview(body: StartRequest = StartRequest()):
    session_id = body.session_id or str(uuid.uuid4())
    try:
        return await ai_engine.start_session(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/respond")
async def respond_to_interview(body: RespondRequest):
    try:
        return await ai_engine.process_response(body.session_id, body.answer)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{session_id}/summary")
async def get_interview_summary(session_id: str):
    try:
        return await ai_engine.get_summary(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
