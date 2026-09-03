import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_admin
from app.models.user import User
from app.models.organization import Department
from app.schemas.organization import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentRead,
)

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("/", response_model=List[DepartmentRead])
def list_departments(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all departments scoped to the authenticated user's tenant (Accessible by all members)."""
    departments = (
        db.query(Department)
        .filter(Department.tenant_id == current_user.tenant_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return departments


@router.post("/", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new department (Requires ADMIN role)."""
    dept = Department(
        tenant_id=admin_user.tenant_id,
        name=payload.name,
        manager_user_id=payload.manager_user_id,
        parent_department_id=payload.parent_department_id,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.get("/{department_id}", response_model=DepartmentRead)
def get_department(
    department_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieve details for a department within user's tenant (Accessible by all members)."""
    dept = (
        db.query(Department)
        .filter(Department.id == department_id, Department.tenant_id == current_user.tenant_id)
        .first()
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
    dept = (
        db.query(Department)
        .filter(Department.id == department_id, Department.tenant_id == admin_user.tenant_id)
        .first()
    )
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department '{department_id}' not found in current tenant.",
        )
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(dept, key, value)
    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a department (Requires ADMIN role)."""
    dept = (
        db.query(Department)
        .filter(Department.id == department_id, Department.tenant_id == admin_user.tenant_id)
        .first()
    )
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department '{department_id}' not found in current tenant.",
        )
    db.delete(dept)
    db.commit()
    return None
