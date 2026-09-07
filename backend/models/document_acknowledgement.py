"""ERD Table 17: Proof of electronic sign-off on company policies."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class AcknowledgementStatus(str, enum.Enum):
    pending = "pending"
    acknowledged = "acknowledged"


class DocumentAcknowledgement(Base):
    __tablename__ = "document_acknowledgements"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    professional_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False, index=True)
    document_title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1.0")
    status: Mapped[AcknowledgementStatus] = mapped_column(
        SAEnum(AcknowledgementStatus, name="acknowledgement_status"), nullable=False, default=AcknowledgementStatus.pending
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
