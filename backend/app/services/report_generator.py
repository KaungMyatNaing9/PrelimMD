# app/services/report_generator.py
# Generates structured intake reports and PDF exports for clinicians.
# Owner: Report teammate
#
# TODO: Report - implement generate(): accept session summary dict, return structured report dict
# TODO: Report - implement to_pdf(): accept structured report dict, return PDF bytes
# TODO: Report - define report schema in app/models/schemas.py (IntakeReport model)
# TODO: Report - add PDF library (reportlab / weasyprint) to requirements.txt


def generate(session_summary: dict) -> dict:
    """Produce a structured intake report from a completed session summary."""
    # TODO: Report - implement
    raise NotImplementedError


def to_pdf(report: dict) -> bytes:
    """Render a structured report as a PDF and return raw bytes."""
    # TODO: Report - implement
    raise NotImplementedError
