import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_admin
from app.models.user import User
from app.models.project import Project, Client, ProjectStatus
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectRead

router = APIRouter(prefix="/assignments", tags=["Assignments & Capacity"])


# ---------------- Project CRUD Endpoints ----------------
@router.get("/projects", response_model=List[ProjectRead])
def list_projects(
    status: Optional[ProjectStatus] = None,
    client_id: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List projects scoped to current tenant (Accessible by all members)."""
    query = db.query(Project).filter(Project.tenant_id == current_user.tenant_id)
    if status:
        query = query.filter(Project.status == status)
    if client_id:
        query = query.filter(Project.client_id == client_id)
    return query.offset(skip).limit(limit).all()


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new project (Requires ADMIN role)."""
    if payload.client_id:
        client = (
            db.query(Client)
            .filter(Client.id == payload.client_id, Client.tenant_id == admin_user.tenant_id)
            .first()
        )
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client '{payload.client_id}' not found in current tenant.",
            )

    # Check for duplicate project code within the tenant
    existing = (
        db.query(Project)
        .filter(Project.code == payload.code, Project.tenant_id == admin_user.tenant_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with code '{payload.code}' already exists in this tenant.",
        )

    project = Project(
        tenant_id=admin_user.tenant_id,
        client_id=payload.client_id,
        name=payload.name,
        code=payload.code,
        status=payload.status,
        start_date=payload.start_date,
        target_end_date=payload.target_end_date,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieve details for a project in current tenant (Accessible by all members)."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.tenant_id == current_user.tenant_id)
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found in current tenant.",
        )
    return project


@router.put("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update project details (Requires ADMIN role)."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.tenant_id == admin_user.tenant_id)
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found in current tenant.",
        )

    if payload.client_id:
        client = (
            db.query(Client)
            .filter(Client.id == payload.client_id, Client.tenant_id == admin_user.tenant_id)
            .first()
        )
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client '{payload.client_id}' not found in current tenant.",
            )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a project (Requires ADMIN role)."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.tenant_id == admin_user.tenant_id)
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found in current tenant.",
        )
    db.delete(project)
    db.commit()
    return None


# ---------------- Capacity Placeholders ----------------
@router.get("/capacity")
def get_capacity_overview(
    current_user: User = Depends(get_current_active_user),
):
    """Query capacity allocations and availability (Accessible by all members)."""
    return {"total_capacity_allocated_pct": 75, "available_headcount": 12}


@router.post("/allocate")
def allocate_capacity(
    payload: dict,
    admin_user: User = Depends(require_admin),
):
    """Allocate a professional to a project (Requires ADMIN role)."""
    return {"status": "allocated", "payload": payload}
