from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class ProfessionalStatus(str, enum.Enum):
    intake = "intake"
    onboarding = "onboarding"
    ready = "ready"
    assigned = "assigned"
    offboarding = "offboarding"
    inactive = "inactive"


class AvailabilityStatus(str, enum.Enum):
    available = "available"
    partially_booked = "partially_booked"
    fully_booked = "fully_booked"


class Professional(Base):
    __tablename__ = "professionals"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[ProfessionalStatus] = mapped_column(
        SAEnum(ProfessionalStatus, name="professional_status"), nullable=False, default=ProfessionalStatus.intake
    )
    availability_status: Mapped[AvailabilityStatus] = mapped_column(
        SAEnum(AvailabilityStatus, name="availability_status"), nullable=False, default=AvailabilityStatus.available
    )
    skills: Mapped[list | dict | None] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")
    user: Mapped["User | None"] = relationship("User", foreign_keys=[user_id], lazy="joined")
    engagements: Mapped[list["Engagement"]] = relationship("Engagement", back_populates="professional", cascade="all, delete-orphan", lazy="selectin")
    assignments: Mapped[list["Assignment"]] = relationship("Assignment", back_populates="professional", cascade="all, delete-orphan", lazy="selectin")
