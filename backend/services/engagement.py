from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.engagement import Engagement
from backend.models.professional import Professional
from backend.schemas.engagement import EngagementCreate
from backend.services.base import TenantScopedService


class EngagementService(TenantScopedService[Engagement]):
    def __init__(self, db: AsyncSession):
        super().__init__(Engagement, db)

    async def create(self, data: EngagementCreate, tenant_id: uuid.UUID | None = None) -> Engagement:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        payload = data.model_dump(exclude_unset=True)
        # Validate professional belongs to tenant
        p = await self.db.execute(
            select(Professional).where(Professional.id == payload["professional_id"], Professional.tenant_id == tid)
        )
        if not p.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="professional_id not found in tenant")
        payload["tenant_id"] = tid
        return await super().create(payload, tenant_id=tid)

    async def update(self, obj_id: uuid.UUID, data: dict, tenant_id: uuid.UUID | None = None) -> Engagement:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        if "professional_id" in data:
            p = await self.db.execute(
                select(Professional).where(Professional.id == data["professional_id"], Professional.tenant_id == tid)
            )
            if not p.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="professional_id not found in tenant")
        return await super().update(obj_id, data, tenant_id=tid)
