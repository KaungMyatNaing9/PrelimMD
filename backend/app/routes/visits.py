# app/routes/visits.py
# Scheduled visit routes — used by the Staff Portal.

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import AssignedForm, AssignFormRequest, ScheduledVisit
from app.services import store

router = APIRouter()


@router.get("", response_model=List[ScheduledVisit])
def list_visits(patient_id: Optional[str] = Query(default=None)):
    """
    Return scheduled visits. Optionally filter by patient_id.
    Staff Portal uses this to show today's/upcoming patient list.
    """
    return store.get_all_visits(patient_id=patient_id)


@router.get("/{visit_id}", response_model=ScheduledVisit)
def get_visit(visit_id: str):
    """Return a single scheduled visit."""
    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")
    return visit


@router.get("/{visit_id}/forms", response_model=List[AssignedForm])
def get_assigned_forms(visit_id: str):
    """Return all forms assigned to a specific visit."""
    visit = store.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found.")
    return store.get_assignments_for_visit(visit_id)
