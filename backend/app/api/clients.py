import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_active_user,
    get_db,
    get_project_repository,
    require_admin,
)
from app.models.user import User
from app.models.project import Client, ClientStatus
from app.repositories.project import ProjectRepository
from app.schemas.project import ClientCreate, ClientUpdate, ClientRead

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("/", response_model=List[ClientRead])
def list_clients(
    status: Optional[ClientStatus] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """List clients scoped to the authenticated user's tenant (Accessible by all members)."""
    return project_repo.list_clients(
        tenant_id=current_user.tenant_id,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    admin_user: User = Depends(require_admin),
    project_repo: ProjectRepository = Depends(get_project_repository),
    db: Session = Depends(get_db),
):
    """Create a new client account (Requires ADMIN role)."""
    client = Client(
        tenant_id=admin_user.tenant_id,
        name=payload.name,
        contact_email=payload.contact_email,
        status=payload.status,
    )
    project_repo.create_client(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientRead)
def get_client(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """Retrieve details for a client in current tenant (Accessible by all members)."""
    client = project_repo.get_client(current_user.tenant_id, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{client_id}' not found in current tenant.",
        )
    return client


@router.put("/{client_id}", response_model=ClientRead)
def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    admin_user: User = Depends(require_admin),
    project_repo: ProjectRepository = Depends(get_project_repository),
    db: Session = Depends(get_db),
):
    """Update client record (Requires ADMIN role)."""
    client = project_repo.get_client(admin_user.tenant_id, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{client_id}' not found in current tenant.",
        )
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    project_repo: ProjectRepository = Depends(get_project_repository),
    db: Session = Depends(get_db),
):
    """Delete a client (Requires ADMIN role)."""
    client = project_repo.get_client(admin_user.tenant_id, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{client_id}' not found in current tenant.",
        )
    project_repo.client_repo.delete(admin_user.tenant_id, client_id)
    db.commit()
    return None
