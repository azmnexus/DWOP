from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.department import Department
from backend.models.user import User
from backend.schemas.department import DepartmentCreate
from backend.services.base import TenantScopedService


class DepartmentService(TenantScopedService[Department]):
    def __init__(self, db: AsyncSession):
        super().__init__(Department, db)

    async def validate_refs(self, data: dict, tenant_id: uuid.UUID):
        # Validate manager_user_id belongs to same tenant
        if data.get("manager_user_id"):
            u = await self.db.execute(select(User).where(User.id == data["manager_user_id"], User.tenant_id == tenant_id))
            if not u.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="manager_user_id not found in tenant")
        # Validate parent belongs to same tenant and no circular
        if data.get("parent_department_id"):
            p = await self.db.execute(select(Department).where(Department.id == data["parent_department_id"], Department.tenant_id == tenant_id))
            parent = p.scalar_one_or_none()
            if not parent:
                raise HTTPException(status_code=400, detail="parent_department_id not found in tenant")
            # prevent self-parent
            if data.get("id") and data["parent_department_id"] == data["id"]:
                raise HTTPException(status_code=400, detail="Department cannot be its own parent")

    async def create(self, data: DepartmentCreate, tenant_id: uuid.UUID | None = None) -> Department:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        payload = data.model_dump(exclude_unset=True)
        await self.validate_refs(payload, tid)
        return await super().create(payload, tenant_id=tid)

    async def update(self, obj_id: uuid.UUID, data: dict, tenant_id: uuid.UUID | None = None) -> Department:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        # include id for circular check
        check = dict(data)
        check["id"] = obj_id
        await self.validate_refs(check, tid)
        return await super().update(obj_id, data, tenant_id=tid)
