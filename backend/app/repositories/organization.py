"""Organization repository for department structures, teams, and hierarchy traversal."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.organization import Department, Team
from app.repositories.base import BaseRepository


class OrganizationRepository:
    """Domain repository managing multi-tenant departments, teams, and hierarchy validation."""

    def __init__(self, db: Session):
        self.db = db
        self.dept_repo = BaseRepository[Department](db, Department)
        self.team_repo = BaseRepository[Team](db, Team)

    # ---------------- Department Operations ----------------
    def get_department(
        self, tenant_id: uuid.UUID, department_id: uuid.UUID
    ) -> Optional[Department]:
        """Fetch department by id strictly scoped to tenant."""
        return self.dept_repo.get_by_id(tenant_id, department_id)

    def get_department_by_name(
        self, tenant_id: uuid.UUID, name: str
    ) -> Optional[Department]:
        """Fetch department by name strictly scoped to tenant."""
        return (
            self.dept_repo._scoped_query(tenant_id)
            .filter(Department.name == name.strip())
            .first()
        )

    def list_departments(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> List[Department]:
        """List departments scoped to tenant with pagination."""
        return self.dept_repo.list_paginated(tenant_id, skip=skip, limit=limit)

    def create_department(self, department: Department) -> Department:
        """Stage department creation without committing."""
        self.db.add(department)
        self.db.flush()
        return department

    def get_parent_ancestor(
        self, tenant_id: uuid.UUID, parent_id: uuid.UUID
    ) -> Optional[Department]:
        """Lookup parent department strictly within the same tenant to prevent cross-tenant cycles."""
        return self.dept_repo.get_by_id(tenant_id, parent_id)

    def update_department(
        self,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
        obj_in: Union[BaseModel, Dict[str, Any]],
    ) -> Optional[Department]:
        """Apply updates to department. Flushes without committing."""
        return self.dept_repo.update(tenant_id, department_id, obj_in)

    def delete_department(
        self, tenant_id: uuid.UUID, department_id: uuid.UUID
    ) -> bool:
        """Delete department if scoped to tenant."""
        return self.dept_repo.delete(tenant_id, department_id)

    # ---------------- Team Operations ----------------
    def get_team(self, tenant_id: uuid.UUID, team_id: uuid.UUID) -> Optional[Team]:
        """Fetch team by id strictly scoped to tenant."""
        return self.team_repo.get_by_id(tenant_id, team_id)

    def get_team_by_name(self, tenant_id: uuid.UUID, name: str) -> Optional[Team]:
        """Fetch team by name strictly scoped to tenant."""
        return (
            self.team_repo._scoped_query(tenant_id)
            .filter(Team.name == name.strip())
            .first()
        )

    def list_teams(
        self,
        tenant_id: uuid.UUID,
        department_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Team]:
        """List teams within tenant, optionally filtered by department."""
        query = self.team_repo._scoped_query(tenant_id)
        if department_id:
            query = query.filter(Team.department_id == department_id)
        return query.offset(skip).limit(limit).all()

    def create_team(self, team: Team) -> Team:
        """Stage team creation without committing."""
        self.db.add(team)
        self.db.flush()
        return team

    def update_team(
        self,
        tenant_id: uuid.UUID,
        team_id: uuid.UUID,
        obj_in: Union[BaseModel, Dict[str, Any]],
    ) -> Optional[Team]:
        """Apply updates to team. Flushes without committing."""
        return self.team_repo.update(tenant_id, team_id, obj_in)

    def delete_team(self, tenant_id: uuid.UUID, team_id: uuid.UUID) -> bool:
        """Delete team if scoped to tenant."""
        return self.team_repo.delete(tenant_id, team_id)
