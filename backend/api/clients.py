import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.dependencies import RequireAdmin, RequireManager, get_current_user
from backend.models.user import User
from backend.schemas.client import ClientCreate, ClientRead, ClientUpdate
from backend.services.client import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])

@router.post("", response_model=ClientRead, status_code=201, dependencies=[Depends(RequireAdmin)])
async def create_client(payload: ClientCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ClientService(db)
    return await svc.create(payload.model_dump(), tenant_id=current.tenant_id)

@router.get("", response_model=list[ClientRead])
async def list_clients(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ClientService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id)
    return items

@router.get("/{client_id}", response_model=ClientRead)
async def get_client(client_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ClientService(db)
    return await svc.get(client_id, tenant_id=current.tenant_id)

@router.patch("/{client_id}", response_model=ClientRead, dependencies=[Depends(RequireManager)])
async def update_client(client_id: uuid.UUID, payload: ClientUpdate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ClientService(db)
    return await svc.update(client_id, payload.model_dump(exclude_unset=True), tenant_id=current.tenant_id)

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(RequireAdmin)])
async def delete_client(client_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ClientService(db)
    await svc.delete(client_id, tenant_id=current.tenant_id)
