import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import RequireManager, get_current_user
from backend.models.user import User
from backend.schemas.assignment import AssignmentCreate, AssignmentRead, AssignmentUpdate
from backend.services.assignment import AssignmentService

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.post("", response_model=AssignmentRead, status_code=201, dependencies=[Depends(RequireManager)])
async def create_assignment(
    payload: AssignmentCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)
):
    """
    Links a professional to a project+team and updates professional.availability_status
    based on cumulative capacity_percentage (0=>available, 1-99=>partially_booked, >=100=>fully_booked).
    """
    svc = AssignmentService(db)
    return await svc.create(payload, tenant_id=current.tenant_id)


@router.get("", response_model=list[AssignmentRead])
async def list_assignments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    svc = AssignmentService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id)
    return items


@router.get("/{assignment_id}", response_model=AssignmentRead)
async def get_assignment(
    assignment_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)
):
    svc = AssignmentService(db)
    return await svc.get(assignment_id, tenant_id=current.tenant_id)


@router.patch("/{assignment_id}", response_model=AssignmentRead, dependencies=[Depends(RequireManager)])
async def update_assignment(
    assignment_id: uuid.UUID,
    payload: AssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    svc = AssignmentService(db)
    return await svc.update(assignment_id, payload.model_dump(exclude_unset=True), tenant_id=current.tenant_id)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(RequireManager)])
async def delete_assignment(
    assignment_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)
):
    svc = AssignmentService(db)
    await svc.delete(assignment_id, tenant_id=current.tenant_id)
