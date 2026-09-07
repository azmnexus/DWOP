from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.assignment import Assignment
from backend.models.professional import Professional
from backend.models.project import Project
from backend.models.team import Team
from backend.schemas.assignment import AssignmentCreate
from backend.services.base import TenantScopedService


class AssignmentService(TenantScopedService[Assignment]):
    def __init__(self, db: AsyncSession):
        super().__init__(Assignment, db)

    async def validate_refs(self, data: dict, tenant_id: uuid.UUID):
        # professional must exist in tenant
        if data.get("professional_id"):
            p = await self.db.execute(
                select(Professional).where(Professional.id == data["professional_id"], Professional.tenant_id == tenant_id)
            )
            if not p.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="professional_id not found in tenant")
        if data.get("project_id"):
            pr = await self.db.execute(
                select(Project).where(Project.id == data["project_id"], Project.tenant_id == tenant_id)
            )
            if not pr.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="project_id not found in tenant")
        if data.get("team_id"):
            t = await self.db.execute(
                select(Team).where(Team.id == data["team_id"], Team.tenant_id == tenant_id)
            )
            if not t.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="team_id not found in tenant")
        # capacity range already validated by Pydantic, but double-check cumulative
        if data.get("capacity_percentage") is not None and not (1 <= data["capacity_percentage"] <= 100):
            raise HTTPException(status_code=400, detail="capacity_percentage must be 1-100")

    async def create(self, data: AssignmentCreate, tenant_id: uuid.UUID | None = None) -> Assignment:
        from backend.core.tenancy import get_tenant_id
        from backend.services.professional import ProfessionalService

        tid = tenant_id or get_tenant_id()
        payload = data.model_dump(exclude_unset=True)
        await self.validate_refs(payload, tid)
        payload["tenant_id"] = tid
        assignment = await super().create(payload, tenant_id=tid)

        # Recalc availability
        prof_service = ProfessionalService(self.db)
        await prof_service.recalc_availability(payload["professional_id"], tenant_id=tid)

        # === Auto-Audit ===
        from backend.services.audit_helpers import emit_audit

        await emit_audit(
            self.db,
            action="ASSIGNMENT_CREATED",
            target_type="Assignment",
            target_id=assignment.id,
            tenant_id=tid,
            metadata={
                "professional_id": str(payload["professional_id"]),
                "project_id": str(payload.get("project_id")),
                "capacity_pct": payload.get("capacity_percentage"),
            },
        )
        return assignment

    async def update(self, obj_id: uuid.UUID, data: dict, tenant_id: uuid.UUID | None = None) -> Assignment:
        from backend.core.tenancy import get_tenant_id
        from backend.services.professional import ProfessionalService

        tid = tenant_id or get_tenant_id()
        await self.validate_refs(data, tid)
        assignment = await super().update(obj_id, data, tenant_id=tid)
        # Recalc for (possibly changed) professional
        prof_id = data.get("professional_id") or assignment.professional_id
        await ProfessionalService(self.db).recalc_availability(prof_id, tenant_id=tid)
        # === Auto-Audit ===
        from backend.services.audit_helpers import emit_audit

        await emit_audit(
            self.db,
            action="ASSIGNMENT_UPDATED",
            target_type="Assignment",
            target_id=assignment.id,
            tenant_id=tid,
            metadata={"updated_fields": list(data.keys())},
        )
        return assignment

    async def delete(self, obj_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> None:
        from backend.services.professional import ProfessionalService

        tid = tenant_id or self._tenant_id()
        assignment = await self.get(obj_id, tenant_id=tid)
        prof_id = assignment.professional_id
        await super().delete(obj_id, tenant_id=tid)
        await ProfessionalService(self.db).recalc_availability(prof_id, tenant_id=tid)
        # === Auto-Audit ===
        from backend.services.audit_helpers import emit_audit

        await emit_audit(
            self.db,
            action="ASSIGNMENT_DELETED",
            target_type="Assignment",
            target_id=obj_id,
            tenant_id=tid,
            metadata={"professional_id": str(prof_id)},
        )
