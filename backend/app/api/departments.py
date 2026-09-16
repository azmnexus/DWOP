import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_admin
from app.models.user import User
from app.schemas.organization import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentRead,
)
from app.services.organization import OrganizationService

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("/", response_model=List[DepartmentRead])
def list_departments(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all departments scoped to the authenticated user's tenant (Accessible by all members)."""
    return OrganizationService(db).list_departments(
        tenant_id=current_user.tenant_id,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new department (Requires ADMIN role)."""
    return OrganizationService(db).create_department(
        tenant_id=admin_user.tenant_id,
        payload=payload,
    )


@router.get("/{department_id}", response_model=DepartmentRead)
def get_department(
    department_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieve details for a department within user's tenant (Accessible by all members)."""
    dept = OrganizationService(db).get_department(
        tenant_id=current_user.tenant_id,
        department_id=department_id,
    )
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department '{department_id}' not found in current tenant.",
        )
    return dept


@router.put("/{department_id}", response_model=DepartmentRead)
def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update department details (Requires ADMIN role)."""
    return OrganizationService(db).update_department(
        tenant_id=admin_user.tenant_id,
        department_id=department_id,
        payload=payload,
    )


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a department (Requires ADMIN role)."""
    OrganizationService(db).delete_department(
        tenant_id=admin_user.tenant_id,
        department_id=department_id,
    )
    return None

