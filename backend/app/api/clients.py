import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_admin
from app.models.user import User
from app.models.project import Client, ClientStatus
from app.schemas.project import ClientCreate, ClientUpdate, ClientRead

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("/", response_model=List[ClientRead])
def list_clients(
    status: Optional[ClientStatus] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List clients scoped to the authenticated user's tenant (Accessible by all members)."""
    query = db.query(Client).filter(Client.tenant_id == current_user.tenant_id)
    if status:
        query = query.filter(Client.status == status)
    return query.offset(skip).limit(limit).all()


@router.post("/", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new client account (Requires ADMIN role)."""
    client = Client(
        tenant_id=admin_user.tenant_id,
        name=payload.name,
        contact_email=payload.contact_email,
        status=payload.status,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientRead)
def get_client(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieve details for a client in current tenant (Accessible by all members)."""
    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.tenant_id == current_user.tenant_id)
        .first()
    )
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
    db: Session = Depends(get_db),
):
    """Update client record (Requires ADMIN role)."""
    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.tenant_id == admin_user.tenant_id)
        .first()
    )
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
    db: Session = Depends(get_db),
):
    """Delete a client (Requires ADMIN role)."""
    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.tenant_id == admin_user.tenant_id)
        .first()
    )
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{client_id}' not found in current tenant.",
        )
    db.delete(client)
    db.commit()
    return None
