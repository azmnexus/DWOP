import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import (
    get_current_active_user,
    require_admin,
    require_admin_or_manager,
)
from app.models.user import User
from app.models.talent import (
    ProfessionalStatus,
    AvailabilityStatus,
)
from app.schemas.talent import (
    ProfessionalCreate,
    ProfessionalUpdate,
    ProfessionalRead,
)
from app.services.people import PeopleService

router = APIRouter(prefix="/people", tags=["People & Intake"])


@router.get("/", response_model=List[ProfessionalRead])
def list_people(
    status_filter: Optional[ProfessionalStatus] = None,
    availability_filter: Optional[AvailabilityStatus] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all professionals scoped to current authenticated tenant."""
    return PeopleService(db).list_people(
        tenant_id=current_user.tenant_id,
        status_filter=status_filter,
        availability_filter=availability_filter,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=ProfessionalRead, status_code=status.HTTP_201_CREATED)
def create_person(
    payload: ProfessionalCreate,
    operator: User = Depends(require_admin_or_manager),
    db: Session = Depends(get_db),
):
    """Intake / register a single professional (Requires ADMIN or MANAGER role)."""
    return PeopleService(db).create_person(
        tenant_id=operator.tenant_id,
        actor_id=operator.id,
        payload=payload,
    )


@router.post("/bulk-import", response_model=List[ProfessionalRead], status_code=status.HTTP_201_CREATED)
def bulk_import_people(
    payload: List[ProfessionalCreate],
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Bulk import an array of professionals in a single atomic database transaction (Requires ADMIN role)."""
    return PeopleService(db).bulk_import_people(
        tenant_id=admin_user.tenant_id,
        actor_id=admin_user.id,
        payload=payload,
    )


@router.get("/{person_id}", response_model=ProfessionalRead)
def get_person_profile(
    person_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieve full professional profile within tenant (Accessible by all authenticated members)."""
    person = PeopleService(db).get_person_by_id(
        tenant_id=current_user.tenant_id,
        person_id=person_id,
    )
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Professional '{person_id}' not found in current tenant.",
        )
    return person


@router.put("/{person_id}", response_model=ProfessionalRead)
def update_person_profile(
    person_id: uuid.UUID,
    payload: ProfessionalUpdate,
    operator: User = Depends(require_admin_or_manager),
    db: Session = Depends(get_db),
):
    """Update professional details or status (Requires ADMIN or MANAGER role)."""
    return PeopleService(db).update_person_profile(
        tenant_id=operator.tenant_id,
        person_id=person_id,
        payload=payload,
    )
