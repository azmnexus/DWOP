"""
Centralized helpers for auto-audit logging and notification dispatch.

Called inline from high-governance service methods after successful mutations.
Both helpers flush to DB but do NOT commit — they piggyback on the caller's
transaction boundary (get_db commits on success, rolls back on failure).

Scope (high-governance entities only):
  - AccessRequest transitions
  - OnboardingRun creation / OnboardingItem status changes
  - Assignment creation / update
  - Professional bulk import
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit import AuditEvent
from backend.models.notification import Notification, NotificationChannel, NotificationStatus


async def emit_audit(
    db: AsyncSession,
    *,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append an immutable audit event to the ledger."""
    meta = dict(metadata or {})
    meta.setdefault("logged_at", datetime.now(timezone.utc).isoformat())

    event = AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_=meta,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()
    return event


async def emit_notification(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
    title: str,
    message: str,
    channel: NotificationChannel = NotificationChannel.in_app,
) -> Notification:
    """
    Create an in-app notification for a user.
    Sprint 0: stored in DB, queried via GET /notifications/mine.
    Future: push via WebSocket / email / Slack.
    """
    notif = Notification(
        tenant_id=tenant_id,
        recipient_user_id=recipient_user_id,
        channel=channel,
        title=title,
        message=message,
        status=NotificationStatus.pending,
    )
    db.add(notif)
    await db.flush()
    # Mark as sent immediately for in_app (no external delivery needed)
    if channel == NotificationChannel.in_app:
        notif.status = NotificationStatus.sent
        notif.sent_at = datetime.now(timezone.utc)
        await db.flush()
    return notif
