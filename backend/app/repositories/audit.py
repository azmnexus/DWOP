"""Audit repository for tenant-scoped, append-only immutable event streams."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditEvent]):
    """Tenant-scoped, append-only repository for audit logging and timeline querying.

    Invariants:
    - Audit records are append-only; update() and delete() raise NotImplementedError.
    - All reads route through _scoped_query(tenant_id).
    - Flushes mutations but never commits transactions.
    """

    def __init__(self, db: Session):
        super().__init__(db, AuditEvent)

    def log_event(
        self,
        tenant_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID],
        action: str,
        target_type: str,
        target_id: uuid.UUID,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Stage an append-only audit event. Flushes without committing."""
        event = AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            event_metadata=metadata or {},
        )
        self.db.add(event)
        self.db.flush()
        return event

    def list_events(
        self,
        tenant_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AuditEvent]:
        """Query tenant audit timeline ordered by timestamp descending."""
        query = self._scoped_query(tenant_id)
        if actor_user_id:
            query = query.filter(AuditEvent.actor_user_id == actor_user_id)
        if action:
            query = query.filter(AuditEvent.action == action)
        if target_type:
            query = query.filter(AuditEvent.target_type == target_type)
        return query.order_by(AuditEvent.timestamp.desc()).offset(skip).limit(limit).all()

    def count_events(
        self,
        tenant_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
    ) -> int:
        """Count tenant audit events matching criteria."""
        query = self._scoped_query(tenant_id)
        if actor_user_id:
            query = query.filter(AuditEvent.actor_user_id == actor_user_id)
        if action:
            query = query.filter(AuditEvent.action == action)
        if target_type:
            query = query.filter(AuditEvent.target_type == target_type)
        return query.count()

    def update(self, *args, **kwargs) -> Optional[AuditEvent]:
        """AuditEvent is append-only and cannot be updated."""
        raise NotImplementedError("AuditEvent records are append-only and immutable.")

    def delete(self, *args, **kwargs) -> bool:
        """AuditEvent is append-only and cannot be deleted."""
        raise NotImplementedError("AuditEvent records are append-only and immutable.")
