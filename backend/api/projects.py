import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.dependencies import RequireManager, get_current_user
from backend.models.user import User
from backend.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from backend.services.project import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("", response_model=ProjectRead, status_code=201, dependencies=[Depends(RequireManager)])
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ProjectService(db)
    return await svc.create(payload, tenant_id=current.tenant_id)

@router.get("", response_model=list[ProjectRead])
async def list_projects(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ProjectService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id)
    return items

@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ProjectService(db)
    return await svc.get(project_id, tenant_id=current.tenant_id)

@router.patch("/{project_id}", response_model=ProjectRead, dependencies=[Depends(RequireManager)])
async def update_project(project_id: uuid.UUID, payload: ProjectUpdate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ProjectService(db)
    return await svc.update(project_id, payload.model_dump(exclude_unset=True), tenant_id=current.tenant_id)

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(RequireManager)])
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = ProjectService(db)
    await svc.delete(project_id, tenant_id=current.tenant_id)
