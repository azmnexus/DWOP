import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import RequireAdmin, RequireManager, get_current_user
from backend.models.user import User
from backend.schemas.professional import (
    BulkImportRequest,
    ProfessionalCreate,
    ProfessionalCreateWithEngagement,
    ProfessionalRead,
    ProfessionalUpdate,
)
from backend.services.professional import ProfessionalService

router = APIRouter(prefix="/professionals", tags=["professionals"])


@router.post("", response_model=ProfessionalRead, status_code=201, dependencies=[Depends(RequireManager)])
async def create_professional(
    payload: ProfessionalCreateWithEngagement,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    svc = ProfessionalService(db)
    return await svc.create_with_engagement(payload, tenant_id=current.tenant_id)


@router.post("/bulk-import", response_model=list[ProfessionalRead], status_code=201, dependencies=[Depends(RequireAdmin)])
async def bulk_import_professionals(
    payload: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Bulk import exactly 10 synthetic professionals + engagements in a single transaction.
    Atomic: all 10 or none. Returns 400 if not exactly 10, 409 on duplicate email.
    """
    svc = ProfessionalService(db)
    created = await svc.bulk_import(payload.professionals, tenant_id=current.tenant_id)
    return created


# Synthetic helper: generate 10 synthetic professionals without client payload (for CLI/demo)
@router.post("/bulk-import/synthetic", response_model=list[ProfessionalRead], status_code=201, dependencies=[Depends(RequireAdmin)])
async def bulk_import_synthetic(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    import random

    first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn", "Avery", "Parker", "Hayden"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    skills_pool = [["python", "react"], ["java", "aws"], ["go", "k8s"], ["typescript", "node"], ["sql", "etl"]]

    svc = ProfessionalService(db)
    items = []
    for i in range(10):
        items.append(
            ProfessionalCreateWithEngagement(
                first_name=random.choice(first_names),
                last_name=f"{random.choice(last_names)}{i}",
                email=f"synthetic_{i}_{uuid.uuid4().hex[:6]}@example.com",
                phone=f"+1-555-010-{1000+i}",
                status="intake",
                skills=random.choice(skills_pool),
                engagement={
                    "engagement_type": random.choice(["employee", "contractor", "working_student"]),
                    "contract_status": "active",
                    "compensation_rate": f"${random.randint(50,150)}/hr",
                },
            )
        )
    return await svc.bulk_import(items, tenant_id=current.tenant_id)


@router.get("", response_model=list[ProfessionalRead])
async def list_professionals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    svc = ProfessionalService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id)
    return items


@router.get("/{professional_id}", response_model=ProfessionalRead)
async def get_professional(
    professional_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)
):
    svc = ProfessionalService(db)
    return await svc.get(professional_id, tenant_id=current.tenant_id)


@router.patch("/{professional_id}", response_model=ProfessionalRead, dependencies=[Depends(RequireManager)])
async def update_professional(
    professional_id: uuid.UUID,
    payload: ProfessionalUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    svc = ProfessionalService(db)
    return await svc.update(professional_id, payload.model_dump(exclude_unset=True), tenant_id=current.tenant_id)


@router.delete("/{professional_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(RequireAdmin)])
async def delete_professional(
    professional_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)
):
    svc = ProfessionalService(db)
    await svc.delete(professional_id, tenant_id=current.tenant_id)
