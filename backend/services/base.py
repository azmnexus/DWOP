"""
Generic tenant-scoped service base.

All entity services inherit tenant isolation automatically:
- create() injects tenant_id from ContextVar if not explicit
- get/list/update/delete always filter by tenant_id
- Prevents cross-tenant leakage at the service layer even if caller forgets.
"""
from __future__ import annotations

import uuid
from typing import Generic, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.tenancy import get_tenant_id

ModelType = TypeVar("ModelType")

class TenantScopedService(Generic[ModelType]):
    def __init__(self, model: type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    def _tenant_id(self, explicit: uuid.UUID | None = None) -> uuid.UUID:
        return explicit or get_tenant_id()

    async def get(self, obj_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> ModelType:
        tid = self._tenant_id(tenant_id)
        # Tenant model has no tenant_id column - handle separately
        if not hasattr(self.model, "tenant_id"):
            result = await self.db.execute(select(self.model).where(self.model.id == obj_id))  # type: ignore[attr-defined]
        else:
            result = await self.db.execute(
                select(self.model).where(self.model.id == obj_id, self.model.tenant_id == tid)  # type: ignore[attr-defined]
            )
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{self.model.__name__} not found")
        return obj

    async def list(self, *, page: int = 1, page_size: int = 20, tenant_id: uuid.UUID | None = None, filters: list | None = None) -> tuple[list[ModelType], int]:
        tid = self._tenant_id(tenant_id)
        filters = filters or []
        base_filters = []
        if hasattr(self.model, "tenant_id"):
            base_filters.append(self.model.tenant_id == tid)  # type: ignore[attr-defined]
        base_filters.extend(filters)

        count_q = select(func.count()).select_from(self.model).where(*base_filters)  # type: ignore[arg-type]
        total = (await self.db.execute(count_q)).scalar_one()

        q = select(self.model).where(*base_filters).offset((page - 1) * page_size).limit(page_size).order_by(self.model.created_at.desc())  # type: ignore[attr-defined]
        items = (await self.db.execute(q)).scalars().all()
        return list(items), total

    async def create(self, data: dict, tenant_id: uuid.UUID | None = None) -> ModelType:
        # Auto-inject tenant_id for tenant-scoped models
        if hasattr(self.model, "tenant_id") and "tenant_id" not in data:
            data["tenant_id"] = self._tenant_id(tenant_id)
        obj = self.model(**data)  # type: ignore[call-arg]
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj_id: uuid.UUID, data: dict, tenant_id: uuid.UUID | None = None) -> ModelType:
        obj = await self.get(obj_id, tenant_id=tenant_id)
        for k, v in data.items():
            if v is not None:
                setattr(obj, k, v)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> None:
        obj = await self.get(obj_id, tenant_id=tenant_id)
        await self.db.delete(obj)
        await self.db.flush()
