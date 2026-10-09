import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.deps import (
    get_organization_service,
    get_current_active_user,
    require_admin,
)
from app.models.user import User
from app.schemas.organization import TeamCreate, TeamUpdate, TeamRead
from app.services.organization import OrganizationService

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("/", response_model=List[TeamRead])
def list_teams(
    department_id: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    service: OrganizationService = Depends(get_organization_service),
):
    """List teams scoped to the authenticated user's tenant (Accessible by all members)."""
    return service.list_teams(
        tenant_id=current_user.tenant_id,
        department_id=department_id,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    admin_user: User = Depends(require_admin),
    service: OrganizationService = Depends(get_organization_service),
):
    """Create a new team (Requires ADMIN role)."""
    return service.create_team(
        tenant_id=admin_user.tenant_id,
        payload=payload,
    )


@router.get("/{team_id}", response_model=TeamRead)
def get_team(
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    service: OrganizationService = Depends(get_organization_service),
):
    """Retrieve details for a team in current tenant (Accessible by all members)."""
    team = service.get_team(
        tenant_id=current_user.tenant_id,
        team_id=team_id,
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
    service: OrganizationService = Depends(get_organization_service),
):
    """Update team details (Requires ADMIN role)."""
    return service.update_team(
        tenant_id=admin_user.tenant_id,
        team_id=team_id,
        payload=payload,
    )


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    service: OrganizationService = Depends(get_organization_service),
):
    """Delete a team (Requires ADMIN role)."""
    service.delete_team(
        tenant_id=admin_user.tenant_id,
        team_id=team_id,
    )
    return None
