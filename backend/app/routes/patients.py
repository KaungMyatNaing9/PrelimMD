# app/routes/patients.py
# Patient lookup routes — used by the Staff Portal.

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import Patient
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
