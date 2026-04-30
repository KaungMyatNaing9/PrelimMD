# app/services/fhir_service.py
# FHIR data wrapper — returns patient EHR data.
# Currently returns mock data. Replace with real OpenMRS calls when Person 1 is ready.
#
# TODO: Person 1 — replace mock_patients and each function body with real FHIR API calls:
#   GET /openmrs/ws/fhir2/R4/{Resource}?patient={id}
#   Auth: admin/Admin123 (or from env)

from typing import Dict, List, Optional

# ── Mock patient database ─────────────────────────────────────────────────────
# Simulates what Person 1 will seed into OpenMRS.

_MOCK_PATIENTS: Dict[str, dict] = {
    "patient-001": {
        "id": "patient-001",
        "name": "Jane Smith",
        "dob": "1985-03-14",
        "gender": "female",
        "phone": "+1-555-0101",
        "email": "jane.smith@email.com",
        "address": "123 Main St, Chicago, IL 60601",
        "ssn": "***-**-1234",
        "insurance_provider": "BlueCross BlueShield",
        "insurance_id": "BCB123456789",
        "emergency_contact_name": "John Smith",
        "emergency_contact_phone": "+1-555-0102",
        "emergency_contact_relation": "Spouse",
    },
    "patient-002": {
        "id": "patient-002",
        "name": "Robert Johnson",
        "dob": "1972-07-22",
        "gender": "male",
        "phone": "+1-555-0201",
        "email": None,
        "address": None,
        "ssn": None,
        "insurance_provider": None,
        "insurance_id": None,
        "emergency_contact_name": None,
        "emergency_contact_phone": None,
        "emergency_contact_relation": None,
    },
    "patient-003": {
        "id": "patient-003",
        "name": "Maria Garcia",
        "dob": "1990-11-05",
        "gender": "female",
        "phone": "+1-555-0301",
        "email": "maria.garcia@email.com",
        "address": "456 Oak Ave, Chicago, IL 60602",
        "ssn": "***-**-5678",
        "insurance_provider": "Aetna",
        "insurance_id": "AET987654321",
        "emergency_contact_name": "Carlos Garcia",
        "emergency_contact_phone": "+1-555-0302",
        "emergency_contact_relation": "Brother",
    },
}

_MOCK_ALLERGIES: Dict[str, List[dict]] = {
    "patient-001": [
        {"substance": "Penicillin", "reaction": "Hives", "severity": "moderate"},
        {"substance": "Latex", "reaction": "Contact dermatitis", "severity": "mild"},
    ],
    "patient-002": [],
    "patient-003": [
        {"substance": "Sulfa drugs", "reaction": "Rash", "severity": "severe"},
    ],
}

_MOCK_MEDICATIONS: Dict[str, List[dict]] = {
    "patient-001": [
        {"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily"},
        {"name": "Metformin", "dosage": "500mg", "frequency": "twice daily"},
    ],
    "patient-002": [
        {"name": "Atorvastatin", "dosage": "20mg", "frequency": "once daily"},
    ],
    "patient-003": [],
}

_MOCK_CONDITIONS: Dict[str, List[dict]] = {
    "patient-001": [
        {"condition": "Type 2 Diabetes", "status": "active", "onset": "2018-01-01"},
        {"condition": "Hypertension", "status": "active", "onset": "2019-06-01"},
    ],
    "patient-002": [
        {"condition": "Hyperlipidemia", "status": "active", "onset": "2020-03-01"},
    ],
    "patient-003": [],
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_patient(patient_id: str) -> Optional[dict]:
    return _MOCK_PATIENTS.get(patient_id)


def get_allergies(patient_id: str) -> List[dict]:
    return _MOCK_ALLERGIES.get(patient_id, [])


def get_medications(patient_id: str) -> List[dict]:
    return _MOCK_MEDICATIONS.get(patient_id, [])


def get_conditions(patient_id: str) -> List[dict]:
    return _MOCK_CONDITIONS.get(patient_id, [])


def get_all(patient_id: str) -> dict:
    """Return all known EHR data for a patient in one call."""
    return {
        "patient": get_patient(patient_id),
        "allergies": get_allergies(patient_id),
        "medications": get_medications(patient_id),
        "conditions": get_conditions(patient_id),
    }
