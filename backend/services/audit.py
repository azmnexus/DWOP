from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.models.audit import AuditEvent
from backend.services.base import TenantScopedService


class AuditService(TenantScopedService[AuditEvent]):
    """
    Append-only audit ledger.
    - log_event() is the SOLE write path; no update/delete methods exposed.
    - Enforces tenant isolation via ContextVar.
    - Enriches metadata with timestamp/IP/agent if provided.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(AuditEvent, db)

    async def log_event(
        self,
        *,
        action: str,
        target_type: str,
        target_id: uuid.UUID | str,
        actor_user_id: uuid.UUID | str | None = None,
        metadata: dict[str, Any] | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> AuditEvent:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        if isinstance(target_id, str):
            target_id = uuid.UUID(target_id)
        if isinstance(actor_user_id, str) and actor_user_id:
            actor_user_id = uuid.UUID(actor_user_id)

        # Normalize metadata - ensure JSONB serializable and append forensic fields
        meta = dict(metadata or {})
        # Guarantee timestamp in metadata for tamper evidence
        if "logged_at" not in meta:
            meta["logged_at"] = datetime.now(timezone.utc).isoformat()

        event = AuditEvent(
            tenant_id=tid,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_=meta,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(event)
        try:
            await self.db.flush()
            await self.db.refresh(event)
        except IntegrityError as e:
            await self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Audit log failed: {e}")
        return event

    # Override to forbid mutation at service layer
    async def update(self, *args, **kwargs):  # type: ignore[override]
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Audit events are immutable - UPDATE forbidden")

    async def delete(self, *args, **kwargs):  # type: ignore[override]
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Audit events are immutable - DELETE forbidden")

    async def list_for_target(self, target_type: str, target_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> list[AuditEvent]:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        result = await self.db.execute(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tid, AuditEvent.target_type == target_type, AuditEvent.target_id == target_id)
            .order_by(AuditEvent.timestamp.asc())
        )
        return list(result.scalars().all())
