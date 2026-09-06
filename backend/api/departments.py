import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.dependencies import RequireManager, get_current_user
from backend.models.user import User
from backend.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate
from backend.services.department import DepartmentService

router = APIRouter(prefix="/departments", tags=["departments"])

@router.post("", response_model=DepartmentRead, status_code=201, dependencies=[Depends(RequireManager)])
async def create_department(payload: DepartmentCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = DepartmentService(db)
    return await svc.create(payload, tenant_id=current.tenant_id)

@router.get("", response_model=list[DepartmentRead])
async def list_departments(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = DepartmentService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id)
    return items

@router.get("/{dept_id}", response_model=DepartmentRead)
async def get_department(dept_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = DepartmentService(db)
    return await svc.get(dept_id, tenant_id=current.tenant_id)

@router.patch("/{dept_id}", response_model=DepartmentRead, dependencies=[Depends(RequireManager)])
async def update_department(dept_id: uuid.UUID, payload: DepartmentUpdate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = DepartmentService(db)
    return await svc.update(dept_id, payload.model_dump(exclude_unset=True), tenant_id=current.tenant_id)

@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(RequireManager)])
async def delete_department(dept_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = DepartmentService(db)
    await svc.delete(dept_id, tenant_id=current.tenant_id)
