from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.document_acknowledgement import AcknowledgementStatus, DocumentAcknowledgement
from backend.models.professional import Professional
from backend.services.base import TenantScopedService

class DocumentAcknowledgementService(TenantScopedService[DocumentAcknowledgement]):
    def __init__(self, db: AsyncSession):
        super().__init__(DocumentAcknowledgement, db)

    async def create(self, data: dict, tenant_id: uuid.UUID | None = None) -> DocumentAcknowledgement:
        from backend.core.tenancy import get_tenant_id
        tid = tenant_id or get_tenant_id()
        prof_id = data.get("professional_id")
        if prof_id:
            result = await self.db.execute(select(Professional).where(Professional.id == prof_id, Professional.tenant_id == tid))
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="professional_id not found in tenant")
        data["tenant_id"] = tid
        data["status"] = AcknowledgementStatus.pending
        return await super().create(data, tenant_id=tid)

    async def acknowledge(self, ack_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> DocumentAcknowledgement:
        from backend.core.tenancy import get_tenant_id
        tid = tenant_id or get_tenant_id()
        ack = await self.get(ack_id, tenant_id=tid)
        if ack.status == AcknowledgementStatus.acknowledged:
            raise HTTPException(status_code=400, detail="Document already acknowledged")
        ack.status = AcknowledgementStatus.acknowledged
        ack.acknowledged_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(ack)
        return ack
