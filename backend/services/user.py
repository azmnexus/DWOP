from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import get_password_hash
from backend.models.user import User
from backend.schemas.user import UserCreate
from backend.services.base import TenantScopedService


class UserService(TenantScopedService[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def create(self, data: UserCreate, tenant_id: uuid.UUID | None = None) -> User:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or data.tenant_id or get_tenant_id()
        # Enforce unique email per tenant
        existing = await self.db.execute(select(User).where(User.tenant_id == tid, User.email == data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists in tenant")
        payload = data.model_dump(exclude_unset=True, exclude={"password", "tenant_id"})
        payload["hashed_password"] = get_password_hash(data.password)
        payload["tenant_id"] = tid
        return await super().create(payload, tenant_id=tid)

    async def get_by_email(self, email: str, tenant_id: uuid.UUID | None) -> User | None:
        # For login: need to search across tenants or scoped? Use tenant hint via domain/slug if needed.
        # Here we scope to tenant if provided, else global search (then verify tenant matches JWT).
        q = select(User).where(User.email == email)
        if tenant_id:
            q = q.where(User.tenant_id == tenant_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none()
