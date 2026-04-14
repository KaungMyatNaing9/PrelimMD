# app/routes/scheduling.py
# HTTP routes for appointment scheduling.
# Owner: Report/Scheduling teammate
#
# TODO: Scheduling - GET  /slots        → return available provider appointment slots
# TODO: Scheduling - POST /book         → book a slot, return confirmation
# TODO: Scheduling - DELETE /book/{id}  → cancel a booking

from fastapi import APIRouter

router = APIRouter()


@router.get("/slots")
def get_available_slots():
    # TODO: Scheduling - call scheduler.get_slots() with provider/date filters
    return {"message": "placeholder — slot retrieval not yet implemented"}


@router.post("/book")
def book_appointment():
    # TODO: Scheduling - call scheduler.book() with patient and slot details
    return {"message": "placeholder — booking not yet implemented"}


@router.delete("/book/{booking_id}")
def cancel_appointment(booking_id: str):
    # TODO: Scheduling - call scheduler.cancel() with booking_id
    return {"booking_id": booking_id, "message": "placeholder — cancellation not yet implemented"}
