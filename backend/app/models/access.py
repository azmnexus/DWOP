import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class IntegrationProvider(str, enum.Enum):
    github = "github"
    slack = "slack"
    trello = "trello"
    google_workspace = "google_workspace"
    m365 = "m365"


class IntegrationAuthType(str, enum.Enum):
    oauth2 = "oauth2"
    api_key = "api_key"
    webhook = "webhook"


class AccessType(str, enum.Enum):
    repository = "repository"
    channel = "channel"
    board = "board"
    drive = "drive"


class AccessRequestStatus(str, enum.Enum):
    requested = "requested"
    approved = "approved"
    provisioning = "provisioning"
    provisioned = "provisioned"
    failed = "failed"
    revoked = "revoked"


class ApprovalOutcome(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(
        Enum(IntegrationProvider, name="integration_provider_enum", native_enum=False),
        nullable=False,
    )
    auth_type = Column(
        Enum(IntegrationAuthType, name="integration_auth_type_enum", native_enum=False),
        nullable=False,
    )
    connection_status = Column(String(50), default="connected", nullable=False)
    health_status = Column(String(50), default="healthy", nullable=False)
    credentials_encrypted = Column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )
    scopes = Column(
        JSON().with_variant(JSONB, "postgresql"),
        default=list,
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = relationship("Tenant")


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
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
    integration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    access_type = Column(
        Enum(AccessType, name="access_type_enum", native_enum=False),
        nullable=False,
    )
    role_or_scope = Column(String(255), nullable=False)
    status = Column(
        Enum(AccessRequestStatus, name="access_request_status_enum", native_enum=False),
        default=AccessRequestStatus.requested,
        nullable=False,
        index=True,
    )
    requested_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    provisioned_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant")
    professional = relationship("Professional")
    integration = relationship("Integration")


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_type = Column(String(50), nullable=False)
    request_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    approver_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    outcome = Column(
        Enum(ApprovalOutcome, name="approval_outcome_enum", native_enum=False),
        nullable=False,
    )
    rationale = Column(String(1000), nullable=True)
    decided_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


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
