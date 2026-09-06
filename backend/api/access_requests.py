import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import RequireAdmin, RequireManager, get_current_user
from backend.models.access import AccessRequest, ApprovalDecision
from backend.models.user import User
from backend.schemas.access import (
    AccessRequestCreate,
    AccessRequestRead,
    AccessTransitionRequest,
    ApprovalDecisionRead,
    IntegrationCreate,
    IntegrationRead,
)
from backend.services.access import AccessRequestService, ApprovalDecisionService
from backend.models.access import Integration

router = APIRouter(prefix="/access-requests", tags=["access-requests"])
integration_router = APIRouter(prefix="/integrations", tags=["integrations"])


@integration_router.post("", response_model=IntegrationRead, status_code=201, dependencies=[Depends(RequireAdmin)])
async def create_integration(payload: IntegrationCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    obj = Integration(tenant_id=current.tenant_id, provider=payload.provider, name=payload.name, config=payload.config or {})
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return obj


@integration_router.get("", response_model=list[IntegrationRead])
async def list_integrations(db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    result = await db.execute(select(Integration).where(Integration.tenant_id == current.tenant_id))
    return result.scalars().all()


@router.post("", response_model=AccessRequestRead, status_code=201, dependencies=[Depends(RequireManager)])
async def create_access_request(payload: AccessRequestCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = AccessRequestService(db)
    return await svc.create(payload.model_dump(exclude_unset=True), requested_by_user_id=current.id, tenant_id=current.tenant_id)


@router.get("", response_model=list[AccessRequestRead])
async def list_access_requests(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = AccessRequestService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id)
    return items


@router.get("/{request_id}", response_model=AccessRequestRead)
async def get_access_request(request_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = AccessRequestService(db)
    return await svc.get(request_id, tenant_id=current.tenant_id)


@router.post("/{request_id}/transition", response_model=AccessRequestRead, dependencies=[Depends(RequireManager)])
async def transition_access_request(request_id: uuid.UUID, payload: AccessTransitionRequest, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    """
    Database-backed state machine: strictly enforces transitions
    requested -> approved -> provisioning -> provisioned (and failed/revoked branches).
    No Celery/Temporal - pure DB constraints + service logic.
    """
    svc = AccessRequestService(db)
    return await svc.transition(request_id, target_status=payload.target_status, actor_user_id=current.id, tenant_id=current.tenant_id, rationale=payload.rationale)


@router.get("/{request_id}/decisions", response_model=list[ApprovalDecisionRead])
async def list_decisions(request_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    result = await db.execute(select(ApprovalDecision).where(ApprovalDecision.request_id == request_id, ApprovalDecision.tenant_id == current.tenant_id))
    return result.scalars().all()
