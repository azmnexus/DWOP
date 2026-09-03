import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_admin
from app.models.user import User
from app.models.organization import Department, Team
from app.schemas.organization import TeamCreate, TeamUpdate, TeamRead

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("/", response_model=List[TeamRead])
def list_teams(
    department_id: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List teams scoped to the authenticated user's tenant (Accessible by all members)."""
    query = db.query(Team).filter(Team.tenant_id == current_user.tenant_id)
    if department_id:
        query = query.filter(Team.department_id == department_id)
    return query.offset(skip).limit(limit).all()


@router.post("/", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new team (Requires ADMIN role)."""
    dept = (
        db.query(Department)
        .filter(Department.id == payload.department_id, Department.tenant_id == admin_user.tenant_id)
        .first()
    )
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department '{payload.department_id}' does not exist in current tenant.",
        )

    team = Team(
        tenant_id=admin_user.tenant_id,
        department_id=payload.department_id,
        name=payload.name,
        team_lead_id=payload.team_lead_id,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/{team_id}", response_model=TeamRead)
def get_team(
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieve details for a team in current tenant (Accessible by all members)."""
    team = (
        db.query(Team)
        .filter(Team.id == team_id, Team.tenant_id == current_user.tenant_id)
        .first()
    )
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{team_id}' not found in current tenant.",
        )
    return team


@router.put("/{team_id}", response_model=TeamRead)
def update_team(
    team_id: uuid.UUID,
    payload: TeamUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update team details (Requires ADMIN role)."""
    team = (
        db.query(Team)
        .filter(Team.id == team_id, Team.tenant_id == admin_user.tenant_id)
        .first()
    )
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{team_id}' not found in current tenant.",
        )
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(team, key, value)
    db.commit()
    db.refresh(team)
    return team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a team (Requires ADMIN role)."""
    team = (
        db.query(Team)
        .filter(Team.id == team_id, Team.tenant_id == admin_user.tenant_id)
        .first()
    )
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{team_id}' not found in current tenant.",
        )
    db.delete(team)
    db.commit()
    return None
