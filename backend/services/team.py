from __future__ import annotations

import uuid
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.department import Department
from backend.models.user import User
from backend.models.team import Team
from backend.schemas.team import TeamCreate
from backend.services.base import TenantScopedService

class TeamService(TenantScopedService[Team]):
    def __init__(self, db: AsyncSession):
        super().__init__(Team, db)

    async def validate(self, data: dict, tenant_id: uuid.UUID):
        if data.get("department_id"):
            d = await self.db.execute(select(Department).where(Department.id == data["department_id"], Department.tenant_id == tenant_id))
            if not d.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="department_id not found in tenant")
        if data.get("team_lead_id"):
            u = await self.db.execute(select(User).where(User.id == data["team_lead_id"], User.tenant_id == tenant_id))
            if not u.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="team_lead_id not found in tenant")

    async def create(self, data: TeamCreate, tenant_id: uuid.UUID | None = None) -> Team:
        from backend.core.tenancy import get_tenant_id
        tid = tenant_id or get_tenant_id()
        payload = data.model_dump(exclude_unset=True)
        await self.validate(payload, tid)
        return await super().create(payload, tenant_id=tid)

    async def update(self, obj_id: uuid.UUID, data: dict, tenant_id: uuid.UUID | None = None) -> Team:
        from backend.core.tenancy import get_tenant_id
        tid = tenant_id or get_tenant_id()
        await self.validate(data, tid)
        return await super().update(obj_id, data, tenant_id=tid)
