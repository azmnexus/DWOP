from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.professional import AvailabilityStatus, Professional
from backend.models.engagement import Engagement, EngagementType, ContractStatus
from backend.models.user import User
from backend.schemas.professional import ProfessionalCreate, ProfessionalCreateWithEngagement
from backend.services.base import TenantScopedService


class ProfessionalService(TenantScopedService[Professional]):
    def __init__(self, db: AsyncSession):
        super().__init__(Professional, db)

    async def validate(self, data: dict, tenant_id: uuid.UUID):
        if data.get("user_id"):
            u = await self.db.execute(select(User).where(User.id == data["user_id"], User.tenant_id == tenant_id))
            if not u.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="user_id not found in tenant")
        if data.get("email"):
            # unique email per tenant for professionals as well
            existing = await self.db.execute(
                select(Professional).where(Professional.tenant_id == tenant_id, Professional.email == data["email"])
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="Professional email already exists in tenant")

    async def create(self, data: ProfessionalCreate | dict, tenant_id: uuid.UUID | None = None) -> Professional:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else dict(data)
        # handle engagement nested key
        payload.pop("engagement", None)
        payload.pop("engagements", None)
        await self.validate(payload, tid)
        return await super().create(payload, tenant_id=tid)

    async def create_with_engagement(
        self, data: ProfessionalCreateWithEngagement, tenant_id: uuid.UUID | None = None
    ) -> Professional:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        payload = data.model_dump(exclude_unset=True, exclude={"engagement"})
        engagement_data = data.engagement or {}
        # Professional
        prof = await self.create(payload, tenant_id=tid)
        # Engagement (auto-create default if not provided)
        eng_payload: dict[str, Any] = {
            "tenant_id": tid,
            "professional_id": prof.id,
            "engagement_type": engagement_data.get("engagement_type", EngagementType.contractor.value),
            "start_date": engagement_data.get("start_date"),
            "end_date": engagement_data.get("end_date"),
            "contract_status": engagement_data.get("contract_status", ContractStatus.active.value),
            "compensation_rate": engagement_data.get("compensation_rate"),
        }
        # Normalize enums
        if isinstance(eng_payload["engagement_type"], str):
            try:
                eng_payload["engagement_type"] = EngagementType(eng_payload["engagement_type"])
            except ValueError:
                eng_payload["engagement_type"] = EngagementType.contractor
        if isinstance(eng_payload["contract_status"], str):
            try:
                eng_payload["contract_status"] = ContractStatus(eng_payload["contract_status"])
            except ValueError:
                eng_payload["contract_status"] = ContractStatus.active

        engagement = Engagement(**eng_payload)
        self.db.add(engagement)
        await self.db.flush()
        await self.db.refresh(prof)
        return prof

    async def bulk_import(self, items: list[ProfessionalCreateWithEngagement], tenant_id: uuid.UUID | None = None) -> list[Professional]:
        """
        Atomic bulk import: inserts exactly 10 professionals + engagements in ONE transaction.
        Rolls back entirely on any failure. Enforces 10 items.
        """
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        if len(items) != 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bulk import requires exactly 10 professionals, got {len(items)}",
            )

        created: list[Professional] = []
        # Use a nested transaction (savepoint) to ensure atomicity; outer get_db commit will finalize
        # But we explicitly flush and rely on exception rollback.
        try:
            for item in items:
                prof = await self.create_with_engagement(item, tenant_id=tid)
                created.append(prof)
            # All 10 succeeded - flush already done per item; if any email dup, exception bubbles and outer rollback triggers
            return created
        except HTTPException:
            # Ensure partial inserts are rolled back - caller will see 400/409 and outer session rollback will revert
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Bulk import failed, rolled back: {str(e)}")

    async def recalc_availability(self, professional_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> Professional:
        """
        Recalculates availability_status based on cumulative capacity of ACTIVE assignments.
        0% -> available, 1-99% -> partially_booked, >=100% -> fully_booked
        """
        from sqlalchemy import func as sa_func
        from backend.models.assignment import Assignment, AssignmentStatus

        tid = tenant_id or self._tenant_id()
        prof = await self.get(professional_id, tenant_id=tid)

        # Sum only active/planned assignments (exclude cancelled/completed)
        result = await self.db.execute(
            select(sa_func.coalesce(sa_func.sum(Assignment.capacity_percentage), 0)).where(
                Assignment.tenant_id == tid,
                Assignment.professional_id == professional_id,
                Assignment.status.in_([AssignmentStatus.active, AssignmentStatus.planned]),
            )
        )
        total = int(result.scalar_one() or 0)
        if total >= 100:
            prof.availability_status = AvailabilityStatus.fully_booked
        elif total > 0:
            prof.availability_status = AvailabilityStatus.partially_booked
        else:
            prof.availability_status = AvailabilityStatus.available

        # Also update professional status if needed: if fully booked, mark assigned
        if total >= 100 and prof.status == AvailabilityStatus.available:
            pass  # Keep status as is; assignment logic controls availability_status only
        await self.db.flush()
        await self.db.refresh(prof)
        return prof
