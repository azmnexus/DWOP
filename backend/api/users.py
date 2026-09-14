import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.dependencies import RequireAdmin, RequireManager, get_current_user
from backend.models.user import User
from backend.schemas.user import UserCreate, UserRead, UserUpdate
from backend.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(RequireAdmin)])
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = UserService(db)
    # Enforce tenant isolation - ignore client-provided tenant_id, use JWT tenant
    obj = await svc.create(payload, tenant_id=current.tenant_id)
    return obj

@router.get("", response_model=list[UserRead], dependencies=[Depends(RequireManager)])
async def list_users(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = UserService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id)
    return items

@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = UserService(db)
    return await svc.get(user_id, tenant_id=current.tenant_id)

@router.patch("/{user_id}", response_model=UserRead, dependencies=[Depends(RequireAdmin)])
async def update_user(user_id: uuid.UUID, payload: UserUpdate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = UserService(db)
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        from backend.core.security import get_password_hash
        data["hashed_password"] = get_password_hash(data.pop("password"))
    return await svc.update(user_id, data, tenant_id=current.tenant_id)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(RequireAdmin)])
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = UserService(db)
    await svc.delete(user_id, tenant_id=current.tenant_id)
