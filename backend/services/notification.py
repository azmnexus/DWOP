from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.notification import Notification, NotificationChannel, NotificationStatus
from backend.models.user import User
from backend.services.base import TenantScopedService


class NotificationService(TenantScopedService[Notification]):
    def __init__(self, db: AsyncSession):
        super().__init__(Notification, db)

    async def create(self, data: dict, tenant_id: uuid.UUID | None = None) -> Notification:
        from backend.core.tenancy import get_tenant_id
        tid = tenant_id or get_tenant_id()
        recipient_id = data.get("recipient_user_id")
        if recipient_id:
            result = await self.db.execute(select(User).where(User.id == recipient_id, User.tenant_id == tid))
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="recipient_user_id not found in tenant")
        data["tenant_id"] = tid
        data["status"] = NotificationStatus.pending
        return await super().create(data, tenant_id=tid)

    async def mark_sent(self, notification_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> Notification:
        from backend.core.tenancy import get_tenant_id
        tid = tenant_id or get_tenant_id()
        notif = await self.get(notification_id, tenant_id=tid)
        notif.status = NotificationStatus.sent
        notif.sent_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(notif)
        return notif

    async def mark_failed(self, notification_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> Notification:
        from backend.core.tenancy import get_tenant_id
        tid = tenant_id or get_tenant_id()
        notif = await self.get(notification_id, tenant_id=tid)
        notif.status = NotificationStatus.failed
        await self.db.flush()
        await self.db.refresh(notif)
        return notif
