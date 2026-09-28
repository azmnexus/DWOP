import uuid
from typing import List, Optional, Set
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.organization import Department, Team
from app.repositories.organization import OrganizationRepository
from app.schemas.organization import (
    DepartmentCreate,
    DepartmentUpdate,
    TeamCreate,
    TeamUpdate,
)


class OrganizationService:
    """Domain service for multi-tenant organizational structure, departments, and teams."""

    def __init__(self, db: Session, repo: Optional[OrganizationRepository] = None):
        self.db = db
        self.repo = repo or OrganizationRepository(db)

    # ---------------- Department Operations ----------------
    def list_departments(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[Department]:
        """List all departments strictly scoped to the tenant."""
        return self.repo.list_departments(tenant_id, skip=skip, limit=limit)

    def get_department(
        self, tenant_id: uuid.UUID, department_id: uuid.UUID
    ) -> Optional[Department]:
        """Retrieve department details strictly scoped to tenant."""
        return self.repo.get_department(tenant_id, department_id)

    def _validate_hierarchy(
        self,
        tenant_id: uuid.UUID,
        dept_id: Optional[uuid.UUID],
        parent_department_id: Optional[uuid.UUID],
    ) -> None:
        """Validate parent department existence and guard against circular hierarchy loops."""
        if not parent_department_id:
            return

        if dept_id and dept_id == parent_department_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A department cannot be its own parent department.",
            )

        # Traverse ancestor tree to guarantee no cycles
        curr_id = parent_department_id
        visited: Set[uuid.UUID] = {dept_id} if dept_id else set()
        while curr_id is not None:
            if curr_id in visited:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Circular dependency detected in department hierarchy.",
                )
            visited.add(curr_id)
            parent = self.repo.get_parent_ancestor(tenant_id, curr_id)
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent department '{curr_id}' not found in current tenant.",
                )
            curr_id = parent.parent_department_id

    def create_department(
        self, tenant_id: uuid.UUID, payload: DepartmentCreate
    ) -> Department:
        """Create a new department within the tenant with hierarchy validation."""
        if payload.parent_department_id:
            self._validate_hierarchy(tenant_id, None, payload.parent_department_id)

        dept = Department(
            tenant_id=tenant_id,
            name=payload.name,
            manager_user_id=payload.manager_user_id,
            parent_department_id=payload.parent_department_id,
        )
        self.repo.create_department(dept)
        self.db.commit()
        self.db.refresh(dept)
        return dept

    def update_department(
        self,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
        payload: DepartmentUpdate,
    ) -> Department:
        """Update department details with circular dependency checks."""
        dept = self.get_department(tenant_id, department_id)
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department '{department_id}' not found in current tenant.",
            )

        update_data = payload.model_dump(exclude_unset=True)
        if "parent_department_id" in update_data:
            self._validate_hierarchy(
                tenant_id, department_id, update_data["parent_department_id"]
            )

        updated_dept = self.repo.update_department(tenant_id, department_id, update_data)
        self.db.commit()
        self.db.refresh(updated_dept)
        return updated_dept

    def delete_department(
        self, tenant_id: uuid.UUID, department_id: uuid.UUID
    ) -> None:
        """Delete a department scoped to tenant."""
        dept = self.get_department(tenant_id, department_id)
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department '{department_id}' not found in current tenant.",
            )
        self.repo.delete_department(tenant_id, department_id)
        self.db.commit()

    # ---------------- Team Operations ----------------
    def list_teams(
        self,
        tenant_id: uuid.UUID,
        department_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Team]:
        """List teams scoped to the tenant, optionally filtered by department."""
        return self.repo.list_teams(tenant_id, department_id, skip=skip, limit=limit)

    def get_team(
        self, tenant_id: uuid.UUID, team_id: uuid.UUID
    ) -> Optional[Team]:
        """Retrieve team details strictly scoped to tenant."""
        return self.repo.get_team(tenant_id, team_id)

    def create_team(
        self, tenant_id: uuid.UUID, payload: TeamCreate
    ) -> Team:
        """Create a new team within an existing department in the tenant."""
        dept = self.get_department(tenant_id, payload.department_id)
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department '{payload.department_id}' does not exist in current tenant.",
            )

        team = Team(
            tenant_id=tenant_id,
            department_id=payload.department_id,
            name=payload.name,
            team_lead_id=payload.team_lead_id,
        )
        self.repo.create_team(team)
        self.db.commit()
        self.db.refresh(team)
        return team

    def update_team(
        self,
        tenant_id: uuid.UUID,
        team_id: uuid.UUID,
        payload: TeamUpdate,
    ) -> Team:
        """Update team details scoped to tenant."""
        team = self.get_team(tenant_id, team_id)
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team '{team_id}' not found in current tenant.",
            )

        update_data = payload.model_dump(exclude_unset=True)
        if "department_id" in update_data and update_data["department_id"] is not None:
            dept = self.get_department(tenant_id, update_data["department_id"])
            if not dept:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Department '{update_data['department_id']}' does not exist in current tenant.",
                )

        updated_team = self.repo.update_team(tenant_id, team_id, update_data)
        self.db.commit()
        self.db.refresh(updated_team)
        return updated_team

    def delete_team(
        self, tenant_id: uuid.UUID, team_id: uuid.UUID
    ) -> None:
        """Delete a team scoped to tenant."""
        team = self.get_team(tenant_id, team_id)
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team '{team_id}' not found in current tenant.",
            )
        self.repo.delete_team(tenant_id, team_id)
        self.db.commit()
