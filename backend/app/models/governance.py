import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class DocumentAcknowledgementStatus(str, enum.Enum):
    pending = "pending"
    acknowledged = "acknowledged"


class NotificationChannel(str, enum.Enum):
    email = "email"
    slack = "slack"
    in_app = "in_app"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class DocumentAcknowledgement(Base):
    """Table 17 in locked DWOP-ERD.
    Tracks signed compliance documents and policies per workforce professional.
    """
    __tablename__ = "document_acknowledgements"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    professional_id = Column(
        UUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_title = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False, default="1.0")
    status = Column(
        Enum(DocumentAcknowledgementStatus, name="doc_ack_status_enum", native_enum=False),
        default=DocumentAcknowledgementStatus.pending,
        nullable=False,
    )
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    professional = relationship("Professional", backref="document_acknowledgements")


class Notification(Base):
    """Table 18 in locked DWOP-ERD.
    Dispatches operational notifications across email, slack, and in-app channels.
    """
    __tablename__ = "notifications"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel = Column(
        Enum(NotificationChannel, name="notification_channel_enum", native_enum=False),
        default=NotificationChannel.in_app,
        nullable=False,
    )
    title = Column(String(255), nullable=False)
    message = Column(String(1000), nullable=False)
    status = Column(
        Enum(NotificationStatus, name="notification_status_enum", native_enum=False),
        default=NotificationStatus.pending,
        nullable=False,
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    recipient = relationship("User", foreign_keys=[recipient_user_id])
