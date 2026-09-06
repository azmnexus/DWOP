from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class EngagementType(str, enum.Enum):
    employee = "employee"
    contractor = "contractor"
    working_student = "working_student"


class ContractStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    terminated = "terminated"


class Engagement(Base):
    __tablename__ = "engagements"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    professional_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    engagement_type: Mapped[EngagementType] = mapped_column(
        SAEnum(EngagementType, name="engagement_type"), nullable=False, default=EngagementType.contractor
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_status: Mapped[ContractStatus] = mapped_column(
        SAEnum(ContractStatus, name="contract_status"), nullable=False, default=ContractStatus.active
    )
    compensation_rate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    professional: Mapped["Professional"] = relationship("Professional", back_populates="engagements", lazy="joined")
