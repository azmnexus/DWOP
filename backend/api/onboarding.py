import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import RequireAdmin, RequireManager, get_current_user
from backend.models.onboarding import OnboardingItem, OnboardingRun
from backend.models.user import User
from backend.schemas.onboarding import (
    ChecklistTemplateItemCreate,
    ChecklistTemplateItemRead,
    OnboardingItemRead,
    OnboardingItemUpdate,
    OnboardingRunCreate,
    OnboardingRunRead,
    OnboardingTemplateCreate,
    OnboardingTemplateRead,
    OnboardingTemplateUpdate,
)
from backend.services.onboarding import ChecklistTemplateItemService, OnboardingService, OnboardingTemplateService

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ---- Templates ----
@router.post("/templates", response_model=OnboardingTemplateRead, status_code=201, dependencies=[Depends(RequireManager)])
async def create_template(payload: OnboardingTemplateCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = OnboardingTemplateService(db)
    return await svc.create(payload.model_dump(), tenant_id=current.tenant_id)


@router.get("/templates", response_model=list[OnboardingTemplateRead])
async def list_templates(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = OnboardingTemplateService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id)
    return items


@router.get("/templates/{template_id}", response_model=OnboardingTemplateRead)
async def get_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = OnboardingTemplateService(db)
    return await svc.get(template_id, tenant_id=current.tenant_id)


@router.patch("/templates/{template_id}", response_model=OnboardingTemplateRead, dependencies=[Depends(RequireManager)])
async def update_template(template_id: uuid.UUID, payload: OnboardingTemplateUpdate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = OnboardingTemplateService(db)
    return await svc.update(template_id, payload.model_dump(exclude_unset=True), tenant_id=current.tenant_id)


@router.delete("/templates/{template_id}", status_code=204, dependencies=[Depends(RequireAdmin)])
async def delete_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = OnboardingTemplateService(db)
    await svc.delete(template_id, tenant_id=current.tenant_id)


# ---- Checklist items ----
@router.post("/templates/{template_id}/items", response_model=ChecklistTemplateItemRead, status_code=201, dependencies=[Depends(RequireManager)])
async def create_checklist_item(template_id: uuid.UUID, payload: ChecklistTemplateItemCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ChecklistTemplateItemService(db)
    data = payload.model_dump(exclude_unset=True)
    data["template_id"] = template_id
    return await svc.create(data, tenant_id=current.tenant_id)


@router.get("/templates/{template_id}/items", response_model=list[ChecklistTemplateItemRead])
async def list_checklist_items(template_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ChecklistTemplateItemService(db)
    return await svc.list_for_template(template_id, tenant_id=current.tenant_id)


# ---- Runs (blueprint instantiation) ----
@router.post("/runs", response_model=OnboardingRunRead, status_code=201, dependencies=[Depends(RequireManager)])
async def instantiate_run(payload: OnboardingRunCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    """
    instantiate_onboarding_run(professional_id, template_id)
    Creates ONBOARDING_RUN + auto-generates ONBOARDING_ITEMs by copying CHECKLIST_TEMPLATE_ITEM definitions.
    Atomic transaction.
    """
    svc = OnboardingService(db)
    run = await svc.instantiate_onboarding_run(
        professional_id=payload.professional_id,
        template_id=payload.template_id,
        assigned_manager_id=payload.assigned_manager_id,
        tenant_id=current.tenant_id,
    )
    return run


@router.get("/runs", response_model=list[OnboardingRunRead])
async def list_runs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    from sqlalchemy import select
    from backend.models.onboarding import OnboardingRun

    result = await db.execute(select(OnboardingRun).where(OnboardingRun.tenant_id == current.tenant_id).order_by(OnboardingRun.created_at.desc()).offset((page-1)*page_size).limit(page_size))
    return result.scalars().all()


@router.get("/runs/{run_id}", response_model=OnboardingRunRead)
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    result = await db.execute(select(OnboardingRun).where(OnboardingRun.id == run_id, OnboardingRun.tenant_id == current.tenant_id))
    run = result.scalar_one_or_none()
    if not run:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="OnboardingRun not found")
    return run


# ---- Items ----
@router.patch("/items/{item_id}", response_model=OnboardingItemRead, dependencies=[Depends(RequireManager)])
async def update_item(item_id: uuid.UUID, payload: OnboardingItemUpdate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = OnboardingService(db)
    return await svc.update_item_status(item_id, status=payload.status, tenant_id=current.tenant_id, blocker_reason=payload.blocker_reason, evidence_ref=payload.evidence_ref, owner_user_id=payload.owner_user_id, due_date=payload.due_date)


@router.get("/runs/{run_id}/items", response_model=list[OnboardingItemRead])
async def list_run_items(run_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    result = await db.execute(select(OnboardingItem).where(OnboardingItem.run_id == run_id, OnboardingItem.tenant_id == current.tenant_id))
    return result.scalars().all()
