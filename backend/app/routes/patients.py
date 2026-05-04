# app/routes/patients.py
# Patient lookup routes — used by the Staff Portal.

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import CreatePatientRequest, Patient
from app.services import store

router = APIRouter()


@router.get("", response_model=List[Patient])
def list_patients():
    """Return all patients in the mock database."""
    return store.get_all_patients()


@router.get("/{patient_id}", response_model=Patient)
def get_patient(patient_id: str):
    """Return a single patient record by ID."""
    patient = store.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")
    return patient


@router.post("", response_model=Patient)
def create_patient(body: CreatePatientRequest):
    """Create a patient record from the staff portal."""
    patient = Patient(
        patient_id=store.new_id("patient-"),
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        date_of_birth=body.date_of_birth,
        gender=body.gender,
        phone=body.phone.strip() if body.phone else None,
        email=body.email.strip() if body.email else None,
        address=body.address.strip() if body.address else None,
        insurance_provider=body.insurance_provider.strip() if body.insurance_provider else None,
        insurance_id=body.insurance_id.strip() if body.insurance_id else None,
        emergency_contact_name=body.emergency_contact_name.strip() if body.emergency_contact_name else None,
        emergency_contact_phone=body.emergency_contact_phone.strip() if body.emergency_contact_phone else None,
        emergency_contact_relation=body.emergency_contact_relation.strip() if body.emergency_contact_relation else None,
    )
    return store.create_patient(patient)
