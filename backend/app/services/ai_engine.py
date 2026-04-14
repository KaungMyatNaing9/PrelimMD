# app/services/ai_engine.py
# Core AI interview engine — drives the conversational pre-screening flow.
# Owner: AI teammate
#
# TODO: AI - implement start_session(): initialise session state, return first question
# TODO: AI - implement process_response(): feed patient answer to LLM, return next action
# TODO: AI - implement get_summary(): produce structured triage output (risk level, chief complaint, recommended routing)
# TODO: AI - add prompt templates in a /prompts/ subdirectory (keep prompts out of business logic)


def start_session(session_id: str) -> dict:
    """Create a new interview session and return the opening question."""
    # TODO: AI - implement
    raise NotImplementedError


def process_response(session_id: str, patient_input: str) -> dict:
    """Process a patient's answer and return the next question or a triage result."""
    # TODO: AI - implement
    raise NotImplementedError


def get_summary(session_id: str) -> dict:
    """Return a structured triage summary for a completed session."""
    # TODO: AI - implement
    raise NotImplementedError
