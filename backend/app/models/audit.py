import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(100), nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_metadata = Column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    tenant = relationship("Tenant")
    actor = relationship("User", foreign_keys=[actor_user_id])
