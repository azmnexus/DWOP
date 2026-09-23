import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.audit import AuditEvent
from app.repositories.audit import AuditRepository


class AuditService:
    """Tenant-scoped, append-only immutable audit logging service (DWOP-013)."""

    def __init__(self, db: Session, repo: Optional[AuditRepository] = None):
        self.db = db
        self.repo = repo or AuditRepository(db)

    def log_event(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID],
        action: str,
        target_type: str,
        target_id: uuid.UUID,
        metadata: Optional[Dict[str, Any]] = None,
        commit: bool = False,
    ) -> AuditEvent:
        """Write an append-only AuditEvent.
        If commit=False (default), leaves transaction open to commit atomically with the caller.
        """
        event = self.repo.log_event(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata,
        )
        if commit:
            self.db.commit()
            self.db.refresh(event)
        return event

    def list_logs(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AuditEvent]:
        """Query tenant-scoped audit timeline ordered by timestamp descending."""
        return self.repo.list_events(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            skip=skip,
            limit=limit,
        )

    def count_logs(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
    ) -> int:
        """Count total matching audit events for tenant."""
        return self.repo.count_events(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
        )
