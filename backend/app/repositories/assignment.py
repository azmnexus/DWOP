"""Assignment repository for capacity allocations, project assignments, and capacity aggregation."""
from __future__ import annotations

import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.assignment import Assignment, AssignmentStatus
from app.repositories.base import BaseRepository


class AssignmentRepository(BaseRepository[Assignment]):
    """Domain repository strictly managing Assignment records and capacity aggregations.

    Invariants:
    - Encapsulates Assignment queries and capacity aggregations ONLY.
    - Foreign-entity lookups (Project, Professional, Team) MUST be resolved via their respective repositories.
    """

    def __init__(self, db: Session):
        super().__init__(db, Assignment)

    def get_active_by_professional(
        self,
        tenant_id: uuid.UUID,
        professional_id: uuid.UUID,
        exclude_assignment_id: Optional[uuid.UUID] = None,
    ) -> List[Assignment]:
        """Fetch active assignments for a professional to evaluate capacity load."""
        query = self._scoped_query(tenant_id).filter(
            Assignment.professional_id == professional_id,
            Assignment.status == AssignmentStatus.active,
        )
        if exclude_assignment_id:
            query = query.filter(Assignment.id != exclude_assignment_id)
        return query.all()

    def sum_active_capacity(
        self,
        tenant_id: uuid.UUID,
        professional_id: uuid.UUID,
        exclude_assignment_id: Optional[uuid.UUID] = None,
    ) -> int:
        """Aggregate total allocated active capacity percentage for a professional."""
        active = self.get_active_by_professional(
            tenant_id=tenant_id,
            professional_id=professional_id,
            exclude_assignment_id=exclude_assignment_id,
        )
        return sum(a.capacity_percentage for a in active)

    def list_assignments(
        self,
        tenant_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
        professional_id: Optional[uuid.UUID] = None,
        team_id: Optional[uuid.UUID] = None,
        status: Optional[AssignmentStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Assignment]:
        """Query assignments with multi-dimensional operational filters."""
        query = self._scoped_query(tenant_id)
        if project_id:
            query = query.filter(Assignment.project_id == project_id)
        if professional_id:
            query = query.filter(Assignment.professional_id == professional_id)
        if team_id:
            query = query.filter(Assignment.team_id == team_id)
        if status:
            query = query.filter(Assignment.status == status)
        return query.order_by(Assignment.created_at.desc()).offset(skip).limit(limit).all()

    def get_all_active_assignments(self, tenant_id: uuid.UUID) -> List[Assignment]:
        """Fetch all currently active assignments in the tenant for global utilization metrics."""
        return (
            self._scoped_query(tenant_id)
            .filter(Assignment.status == AssignmentStatus.active)
            .all()
        )
