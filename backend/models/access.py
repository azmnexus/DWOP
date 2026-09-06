from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


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


class AccessType(str, enum.Enum):
    repository = "repository"
    channel = "channel"
    board = "board"
    drive = "drive"
    generic = "generic"


# Minimal Integration stub for FK integrity - matches spec's integration_id
class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="github")
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, index=True)
    access_type: Mapped[AccessType] = mapped_column(SAEnum(AccessType, name="access_type"), nullable=False, default=AccessType.generic)
    role_or_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AccessRequestStatus] = mapped_column(SAEnum(AccessRequestStatus, name="access_request_status"), nullable=False, default=AccessRequestStatus.requested, index=True)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    provisioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    professional: Mapped["Professional"] = relationship("Professional", lazy="joined")
    integration: Mapped["Integration"] = relationship("Integration", lazy="joined")


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "access_request"
    request_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    approver_user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    outcome: Mapped[ApprovalOutcome] = mapped_column(SAEnum(ApprovalOutcome, name="approval_outcome"), nullable=False)
    rationale: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    approver: Mapped["User"] = relationship("User", foreign_keys=[approver_user_id], lazy="joined")
