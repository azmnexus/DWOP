import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import RequireManager, get_current_user
from backend.models.user import User
from backend.schemas.engagement import EngagementCreate, EngagementRead, EngagementUpdate
from backend.services.engagement import EngagementService

router = APIRouter(prefix="/engagements", tags=["engagements"])


@router.post("", response_model=EngagementRead, status_code=201, dependencies=[Depends(RequireManager)])
async def create_engagement(
    payload: EngagementCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)
):
    svc = EngagementService(db)
    return await svc.create(payload, tenant_id=current.tenant_id)


@router.get("", response_model=list[EngagementRead])
async def list_engagements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    svc = EngagementService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id)
    return items


@router.get("/{engagement_id}", response_model=EngagementRead)
async def get_engagement(
    engagement_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)
):
    svc = EngagementService(db)
    return await svc.get(engagement_id, tenant_id=current.tenant_id)


@router.patch("/{engagement_id}", response_model=EngagementRead, dependencies=[Depends(RequireManager)])
async def update_engagement(
    engagement_id: uuid.UUID,
    payload: EngagementUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    svc = EngagementService(db)
    return await svc.update(engagement_id, payload.model_dump(exclude_unset=True), tenant_id=current.tenant_id)


@router.delete("/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(RequireManager)])
async def delete_engagement(
    engagement_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)
):
    svc = EngagementService(db)
    await svc.delete(engagement_id, tenant_id=current.tenant_id)
