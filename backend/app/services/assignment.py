import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.talent import Professional, ProfessionalStatus, AvailabilityStatus
from app.models.project import Project
from app.models.organization import Team
from app.models.assignment import Assignment, AssignmentStatus
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentRead,
    CapacityOverviewRead,
    ProfessionalCapacityRead,
)
from app.services.audit import AuditService


class AssignmentService:
    """Domain service managing workforce capacity allocations and threshold rules."""

    def __init__(self, db: Session):
        self.db = db

    def get_active_capacity(
        self,
        tenant_id: uuid.UUID,
        professional_id: uuid.UUID,
        exclude_assignment_id: Optional[uuid.UUID] = None,
    ) -> int:
        """Sum total allocated capacity percentage for active assignments."""
        query = self.db.query(Assignment).filter(
            Assignment.tenant_id == tenant_id,
            Assignment.professional_id == professional_id,
            Assignment.status == AssignmentStatus.active,
        )
        if exclude_assignment_id:
            query = query.filter(Assignment.id != exclude_assignment_id)
        active_assignments = query.all()
        return sum(a.capacity_percentage for a in active_assignments)

    def recalculate_availability(self, professional: Professional) -> AvailabilityStatus:
        """Recalculate and update the availability status for a professional."""
        total_active_cap = self.get_active_capacity(professional.tenant_id, professional.id)
        if total_active_cap == 0:
            professional.availability_status = AvailabilityStatus.available
        elif total_active_cap < 100:
            professional.availability_status = AvailabilityStatus.partially_booked
        else:
            professional.availability_status = AvailabilityStatus.fully_booked
        return professional.availability_status

    def _enrich_assignment(self, assignment: Assignment) -> AssignmentRead:
        """Attach related names for serializing enriched AssignmentRead."""
        prof_name = f"{assignment.professional.first_name} {assignment.professional.last_name}" if assignment.professional else None
        proj_name = assignment.project.name if assignment.project else None
        proj_code = assignment.project.code if assignment.project else None
        read_obj = AssignmentRead.model_validate(assignment)
        read_obj.professional_name = prof_name
        read_obj.project_name = proj_name
        read_obj.project_code = proj_code
        return read_obj

    def allocate_capacity(
        self,
        tenant_id: uuid.UUID,
        payload: AssignmentCreate,
        actor: User,
    ) -> AssignmentRead:
        """Allocate a professional's capacity to a project.
        Enforces maximum 100% capacity rule across active allocations.
        Logs an immutable audit event strictly inside the database transaction.
        """
        # 1. Validate Professional in tenant
        prof = (
            self.db.query(Professional)
            .filter(
                Professional.id == payload.professional_id,
                Professional.tenant_id == tenant_id,
            )
            .first()
        )
        if not prof:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Professional '{payload.professional_id}' not found in current tenant.",
            )

        # 2. Validate Project in tenant
        proj = (
            self.db.query(Project)
            .filter(
                Project.id == payload.project_id,
                Project.tenant_id == tenant_id,
            )
            .first()
        )
        if not proj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{payload.project_id}' not found in current tenant.",
            )

        # 3. Validate Team if provided
        if payload.team_id:
            team = (
                self.db.query(Team)
                .filter(
                    Team.id == payload.team_id,
                    Team.tenant_id == tenant_id,
                )
                .first()
            )
            if not team:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Team '{payload.team_id}' not found in current tenant.",
                )

        # 4. Strict Capacity Limit Check (Maximum 100%)
        current_capacity = self.get_active_capacity(tenant_id, prof.id)
        projected_capacity = current_capacity + payload.capacity_percentage
        if projected_capacity > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Capacity limit exceeded: Professional '{prof.first_name} {prof.last_name}' "
                    f"currently has {current_capacity}% active allocation. "
                    f"Allocating {payload.capacity_percentage}% would result in {projected_capacity}%, "
                    f"exceeding the maximum allowed 100% threshold."
                ),
            )

        # 5. Create Assignment record
        assignment = Assignment(
            tenant_id=tenant_id,
            professional_id=payload.professional_id,
            project_id=payload.project_id,
            team_id=payload.team_id,
            role_on_project=payload.role_on_project,
            capacity_percentage=payload.capacity_percentage,
            start_date=payload.start_date,
            end_date=payload.end_date,
            status=AssignmentStatus.active,
        )
        self.db.add(assignment)
        self.db.flush()

        # 6. Recalculate Professional Availability & Advance Lifecycle
        self.recalculate_availability(prof)
        if prof.status in (ProfessionalStatus.ready, ProfessionalStatus.intake):
            prof.status = ProfessionalStatus.assigned

        # 7. Atomic Audit Logging strictly inside transaction
        AuditService(self.db).log_event(
            tenant_id=tenant_id,
            actor_user_id=actor.id,
            action="assignment.allocated",
            target_type="Assignment",
            target_id=assignment.id,
            metadata={
                "professional_id": str(prof.id),
                "project_id": str(proj.id),
                "project_code": proj.code,
                "role_on_project": assignment.role_on_project,
                "capacity_percentage": assignment.capacity_percentage,
                "total_allocated_capacity_pct": projected_capacity,
                "availability_status": prof.availability_status.value,
            },
            commit=False,
        )

        self.db.commit()
        self.db.refresh(assignment)
        return self._enrich_assignment(assignment)

    def update_assignment(
        self,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        payload: AssignmentUpdate,
        actor: User,
    ) -> AssignmentRead:
        """Update an existing assignment (capacity adjustment, completion, reassignment).
        Enforces 100% capacity ceiling and logs audit event inside transaction.
        """
        assignment = (
            self.db.query(Assignment)
            .filter(
                Assignment.id == assignment_id,
                Assignment.tenant_id == tenant_id,
            )
            .first()
        )
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment '{assignment_id}' not found in current tenant.",
            )

        prof = assignment.professional
        target_capacity = (
            payload.capacity_percentage
            if payload.capacity_percentage is not None
            else assignment.capacity_percentage
        )
        target_status = payload.status if payload.status is not None else assignment.status

        # Capacity validation if active
        if target_status == AssignmentStatus.active:
            other_capacity = self.get_active_capacity(
                tenant_id,
                prof.id,
                exclude_assignment_id=assignment.id,
            )
            projected = other_capacity + target_capacity
            if projected > 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Capacity limit exceeded: Updating assignment to {target_capacity}% "
                        f"would result in {projected}% total allocation for '{prof.first_name} {prof.last_name}' "
                        f"(maximum allowed is 100%)."
                    ),
                )

        # Apply updates
        old_status = assignment.status
        old_capacity = assignment.capacity_percentage
        if payload.role_on_project is not None:
            assignment.role_on_project = payload.role_on_project
        if payload.capacity_percentage is not None:
            assignment.capacity_percentage = payload.capacity_percentage
        if payload.end_date is not None:
            assignment.end_date = payload.end_date
        if payload.status is not None:
            assignment.status = payload.status

        self.db.flush()

        # Recalculate Professional Availability
        self.recalculate_availability(prof)
        total_remaining_active = self.get_active_capacity(tenant_id, prof.id)
        if total_remaining_active == 0 and prof.status == ProfessionalStatus.assigned:
            prof.status = ProfessionalStatus.ready

        # Atomic Audit Logging
        AuditService(self.db).log_event(
            tenant_id=tenant_id,
            actor_user_id=actor.id,
            action="assignment.updated",
            target_type="Assignment",
            target_id=assignment.id,
            metadata={
                "professional_id": str(prof.id),
                "old_status": old_status.value if hasattr(old_status, "value") else str(old_status),
                "new_status": assignment.status.value if hasattr(assignment.status, "value") else str(assignment.status),
                "old_capacity": old_capacity,
                "new_capacity": assignment.capacity_percentage,
                "total_active_capacity_pct": total_remaining_active,
                "availability_status": prof.availability_status.value,
            },
            commit=False,
        )

        self.db.commit()
        self.db.refresh(assignment)
        return self._enrich_assignment(assignment)

    def list_assignments(
        self,
        tenant_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None,
        professional_id: Optional[uuid.UUID] = None,
        status_filter: Optional[AssignmentStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AssignmentRead]:
        """List assignments with optional filters, enriched with names."""
        query = self.db.query(Assignment).filter(Assignment.tenant_id == tenant_id)
        if project_id:
            query = query.filter(Assignment.project_id == project_id)
        if professional_id:
            query = query.filter(Assignment.professional_id == professional_id)
        if status_filter:
            query = query.filter(Assignment.status == status_filter)
        assignments = query.offset(skip).limit(limit).all()
        return [self._enrich_assignment(a) for a in assignments]

    def get_capacity_overview(self, tenant_id: uuid.UUID) -> CapacityOverviewRead:
        """Compute aggregate platform-wide capacity statistics for current tenant."""
        all_profs = self.db.query(Professional).filter(Professional.tenant_id == tenant_id).all()
        total_profs = len(all_profs)
        avail = sum(1 for p in all_profs if p.availability_status == AvailabilityStatus.available)
        part = sum(1 for p in all_profs if p.availability_status == AvailabilityStatus.partially_booked)
        full = sum(1 for p in all_profs if p.availability_status == AvailabilityStatus.fully_booked)

        active_assignments = (
            self.db.query(Assignment)
            .filter(
                Assignment.tenant_id == tenant_id,
                Assignment.status == AssignmentStatus.active,
            )
            .all()
        )
        total_active_count = len(active_assignments)
        sum_allocated_capacity = sum(a.capacity_percentage for a in active_assignments)
        avg_utilization = round(sum_allocated_capacity / total_profs, 2) if total_profs > 0 else 0.0

        return CapacityOverviewRead(
            total_professionals=total_profs,
            available_headcount=avail,
            partially_booked_headcount=part,
            fully_booked_headcount=full,
            total_active_allocations=total_active_count,
            average_utilization_pct=avg_utilization,
        )

    def get_professional_capacity(
        self,
        tenant_id: uuid.UUID,
        professional_id: uuid.UUID,
    ) -> ProfessionalCapacityRead:
        """Detailed capacity breakdown for an individual professional."""
        prof = (
            self.db.query(Professional)
            .filter(
                Professional.id == professional_id,
                Professional.tenant_id == tenant_id,
            )
            .first()
        )
        if not prof:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Professional '{professional_id}' not found in current tenant.",
            )

        active_alloc = self.get_active_capacity(tenant_id, prof.id)
        assignments = (
            self.db.query(Assignment)
            .filter(
                Assignment.tenant_id == tenant_id,
                Assignment.professional_id == prof.id,
            )
            .all()
        )

        return ProfessionalCapacityRead(
            professional_id=prof.id,
            first_name=prof.first_name,
            last_name=prof.last_name,
            email=prof.email,
            availability_status=prof.availability_status.value,
            total_allocated_capacity_pct=active_alloc,
            remaining_capacity_pct=max(0, 100 - active_alloc),
            active_assignments_count=sum(1 for a in assignments if a.status == AssignmentStatus.active),
            assignments=[self._enrich_assignment(a) for a in assignments],
        )
