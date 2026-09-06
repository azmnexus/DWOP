from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from backend.models.tenant import Tenant
from backend.schemas.tenant import TenantCreate, TenantUpdate
from backend.services.base import TenantScopedService

class TenantService(TenantScopedService[Tenant]):
    def __init__(self, db: AsyncSession):
        super().__init__(Tenant, db)

    async def create(self, data: TenantCreate) -> Tenant:
        # Enforce unique slug/domain at service level for clean 409
        existing = await self.db.execute(select(Tenant).where(Tenant.slug == data.slug))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant slug already exists")
        if data.domain:
            existing2 = await self.db.execute(select(Tenant).where(Tenant.domain == data.domain))
            if existing2.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant domain already exists")
        return await super().create(data.model_dump(exclude_unset=True), tenant_id=None)

    async def list_all(self, page: int = 1, page_size: int = 20):
        # Tenants are NOT tenant-scoped - override to avoid tenant_id filter
        return await super().list(page=page, page_size=page_size, tenant_id=None, filters=[])

    async def get_by_slug(self, slug: str) -> Tenant:
        result = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        obj = result.scalar_one_or_none()
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        return obj
