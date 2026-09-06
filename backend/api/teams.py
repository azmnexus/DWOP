import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.dependencies import RequireManager, get_current_user
from backend.models.user import User
from backend.schemas.team import TeamCreate, TeamRead, TeamUpdate
from backend.services.team import TeamService

router = APIRouter(prefix="/teams", tags=["teams"])

@router.post("", response_model=TeamRead, status_code=201, dependencies=[Depends(RequireManager)])
async def create_team(payload: TeamCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = TeamService(db)
    return await svc.create(payload, tenant_id=current.tenant_id)

@router.get("", response_model=list[TeamRead])
async def list_teams(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = TeamService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id)
    return items

@router.get("/{team_id}", response_model=TeamRead)
async def get_team(team_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = TeamService(db)
    return await svc.get(team_id, tenant_id=current.tenant_id)

@router.patch("/{team_id}", response_model=TeamRead, dependencies=[Depends(RequireManager)])
async def update_team(team_id: uuid.UUID, payload: TeamUpdate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = TeamService(db)
    return await svc.update(team_id, payload.model_dump(exclude_unset=True), tenant_id=current.tenant_id)

@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(RequireManager)])
async def delete_team(team_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = TeamService(db)
    await svc.delete(team_id, tenant_id=current.tenant_id)
