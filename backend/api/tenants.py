import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.dependencies import RequireAdmin, get_current_user
from backend.models.user import User
from backend.schemas.tenant import TenantCreate, TenantRead, TenantUpdate
from backend.services.tenant import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])

@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(RequireAdmin)])
async def create_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_db)):
    svc = TenantService(db)
    obj = await svc.create(payload)
    return obj

@router.post("/bootstrap", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
async def bootstrap_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_db)):
    """Allow first tenant creation without auth for bootstrapping (remove in prod or guard via super-admin)."""
    svc = TenantService(db)
    obj = await svc.create(payload)
    return obj

@router.get("", response_model=list[TenantRead])
async def list_tenants(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    svc = TenantService(db)
    items, _ = await svc.list_all(page=page, page_size=page_size)
    return items

@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    svc = TenantService(db)
    return await svc.get(tenant_id)

@router.patch("/{tenant_id}", response_model=TenantRead, dependencies=[Depends(RequireAdmin)])
async def update_tenant(tenant_id: uuid.UUID, payload: TenantUpdate, db: AsyncSession = Depends(get_db)):
    svc = TenantService(db)
    return await svc.update(tenant_id, payload.model_dump(exclude_unset=True))

@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(RequireAdmin)])
async def delete_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    svc = TenantService(db)
    await svc.delete(tenant_id)
