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
    Professional,
    Engagement,
    ProfessionalStatus,
    AvailabilityStatus,
)
from app.schemas.talent import (
    ProfessionalCreate,
    ProfessionalUpdate,
    ProfessionalRead,
)

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
    query = db.query(Professional).filter(Professional.tenant_id == current_user.tenant_id)
    if status_filter:
        query = query.filter(Professional.status == status_filter)
    if availability_filter:
        query = query.filter(Professional.availability_status == availability_filter)
    return query.offset(skip).limit(limit).all()


@router.post("/", response_model=ProfessionalRead, status_code=status.HTTP_201_CREATED)
def create_person(
    payload: ProfessionalCreate,
    operator: User = Depends(require_admin_or_manager),
    db: Session = Depends(get_db),
):
    """Intake / register a single professional (Requires ADMIN or MANAGER role)."""
    # Check if a professional with this email already exists in the same tenant
    existing = (
        db.query(Professional)
        .filter(
            Professional.email == payload.email,
            Professional.tenant_id == operator.tenant_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Professional with email '{payload.email}' already exists in this tenant.",
        )

    professional = Professional(
        tenant_id=operator.tenant_id,
        user_id=payload.user_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        status=payload.status,
        availability_status=payload.availability_status,
        skills=payload.skills,
    )
    db.add(professional)
    db.flush()  # populate professional.id for engagement FK

    if payload.engagement:
        engagement = Engagement(
            tenant_id=operator.tenant_id,
            professional_id=professional.id,
            engagement_type=payload.engagement.engagement_type,
            start_date=payload.engagement.start_date,
            end_date=payload.engagement.end_date,
            contract_status=payload.engagement.contract_status,
            compensation_rate=payload.engagement.compensation_rate,
        )
        db.add(engagement)

    db.commit()
    db.refresh(professional)
    return professional


@router.post("/bulk-import", response_model=List[ProfessionalRead], status_code=status.HTTP_201_CREATED)
def bulk_import_people(
    payload: List[ProfessionalCreate],
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Bulk import an array of professionals in a single atomic database transaction (Requires ADMIN role)."""
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload array cannot be empty.",
        )

    created_records = []
    try:
        for item in payload:
            # Check existing email in tenant to prevent conflicts
            existing = (
                db.query(Professional)
                .filter(
                    Professional.email == item.email,
                    Professional.tenant_id == admin_user.tenant_id,
                )
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Duplicate detected: Professional with email '{item.email}' already exists.",
                )

            prof = Professional(
                tenant_id=admin_user.tenant_id,
                user_id=item.user_id,
                first_name=item.first_name,
                last_name=item.last_name,
                email=item.email,
                phone=item.phone,
                status=item.status,
                availability_status=item.availability_status,
                skills=item.skills,
            )
            db.add(prof)
            db.flush()

            if item.engagement:
                eng = Engagement(
                    tenant_id=admin_user.tenant_id,
                    professional_id=prof.id,
                    engagement_type=item.engagement.engagement_type,
                    start_date=item.engagement.start_date,
                    end_date=item.engagement.end_date,
                    contract_status=item.engagement.contract_status,
                    compensation_rate=item.engagement.compensation_rate,
                )
                db.add(eng)

            created_records.append(prof)

        db.commit()
        for record in created_records:
            db.refresh(record)
        return created_records

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute bulk import transaction: {str(e)}",
        )


@router.get("/{person_id}", response_model=ProfessionalRead)
def get_person_profile(
    person_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieve full professional profile within tenant (Accessible by all authenticated members)."""
    person = (
        db.query(Professional)
        .filter(
            Professional.id == person_id,
            Professional.tenant_id == current_user.tenant_id,
        )
        .first()
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
    person = (
        db.query(Professional)
        .filter(
            Professional.id == person_id,
            Professional.tenant_id == operator.tenant_id,
        )
        .first()
    )
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Professional '{person_id}' not found in current tenant.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(person, key, value)

    db.commit()
    db.refresh(person)
    return person
