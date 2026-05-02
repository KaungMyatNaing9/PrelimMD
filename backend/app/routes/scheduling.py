# app/routes/scheduling.py
# NOTE: This module has been repurposed.
#
# The original appointment scheduling stubs (GET /slots, POST /book, DELETE /book/{id})
# have been replaced by the post-discharge follow-up scheduler, which lives at:
#   GET  /followups
#   GET  /followups/{task_id}
#   POST /followups/schedule
#   GET  /followups/question-bank
#
# This file is kept as a thin compatibility shim that redirects to the follow-up
# router for any legacy call patterns. If Twilio or a real calendar integration
# is added later, real scheduling logic can go here.

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/slots")
def get_slots():
    return JSONResponse(
        status_code=410,
        content={
            "message": "This endpoint has been replaced. Use GET /followups for follow-up task management.",
            "new_endpoints": {
                "list_followups": "GET /followups",
                "schedule_followup": "POST /followups/schedule",
                "question_bank": "GET /followups/question-bank",
            },
        },
    )


@router.post("/book")
def book_appointment():
    return JSONResponse(
        status_code=410,
        content={
            "message": "This endpoint has been replaced. Use POST /followups/schedule to schedule follow-up calls.",
        },
    )


@router.delete("/book/{booking_id}")
def cancel_appointment(booking_id: str):
    return JSONResponse(
        status_code=410,
        content={
            "message": "This endpoint has been replaced.",
        },
    )
