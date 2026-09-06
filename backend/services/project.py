from __future__ import annotations

import uuid
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.client import Client
from backend.models.project import Project
from backend.schemas.project import ProjectCreate
from backend.services.base import TenantScopedService

class ProjectService(TenantScopedService[Project]):
    def __init__(self, db: AsyncSession):
        super().__init__(Project, db)

    async def validate(self, data: dict, tenant_id: uuid.UUID):
        if data.get("client_id"):
            c = await self.db.execute(select(Client).where(Client.id == data["client_id"], Client.tenant_id == tenant_id))
            if not c.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="client_id not found in tenant")

    async def create(self, data: ProjectCreate, tenant_id: uuid.UUID | None = None) -> Project:
        from backend.core.tenancy import get_tenant_id
        tid = tenant_id or get_tenant_id()
        payload = data.model_dump(exclude_unset=True)
        await self.validate(payload, tid)
        # check unique code per tenant
        existing = await self.db.execute(select(Project).where(Project.tenant_id == tid, Project.code == payload["code"]))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Project code already exists in tenant")
        return await super().create(payload, tenant_id=tid)

    async def update(self, obj_id: uuid.UUID, data: dict, tenant_id: uuid.UUID | None = None) -> Project:
        from backend.core.tenancy import get_tenant_id
        tid = tenant_id or get_tenant_id()
        if "client_id" in data:
            await self.validate(data, tid)
        if "code" in data and data["code"]:
            existing = await self.db.execute(select(Project).where(Project.tenant_id == tid, Project.code == data["code"], Project.id != obj_id))
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="Project code already exists in tenant")
        return await super().update(obj_id, data, tenant_id=tid)
