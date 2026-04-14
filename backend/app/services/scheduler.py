# app/services/scheduler.py
# Manages provider availability and patient appointment booking.
# Owner: Report/Scheduling teammate
#
# TODO: Scheduling - implement get_slots(): query available provider slots (date/provider filters)
# TODO: Scheduling - implement book(): reserve a slot and return booking confirmation
# TODO: Scheduling - implement cancel(): release a booked slot
# TODO: Scheduling - decide on calendar integration (Google Calendar, in-DB slots, etc.)


def get_slots(provider_id: str | None = None, date: str | None = None) -> list:
    """Return a list of available appointment slots."""
    # TODO: Scheduling - implement
    raise NotImplementedError


def book(slot_id: str, patient_info: dict) -> dict:
    """Reserve an appointment slot and return confirmation details."""
    # TODO: Scheduling - implement
    raise NotImplementedError


def cancel(booking_id: str) -> bool:
    """Cancel an existing booking. Returns True on success."""
    # TODO: Scheduling - implement
    raise NotImplementedError
