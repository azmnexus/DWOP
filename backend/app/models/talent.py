import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


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


class EngagementType(str, enum.Enum):
    employee = "employee"
    contractor = "contractor"
    working_student = "working_student"


class ContractStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    terminated = "terminated"


class Professional(Base):
    __tablename__ = "professionals"

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
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    status = Column(
        Enum(ProfessionalStatus, name="professional_status_enum", native_enum=False),
        default=ProfessionalStatus.intake,
        nullable=False,
    )
    availability_status = Column(
        Enum(AvailabilityStatus, name="availability_status_enum", native_enum=False),
        default=AvailabilityStatus.available,
        nullable=False,
    )
    skills = Column(
        JSON().with_variant(JSONB, "postgresql"),
        default=list,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("User", foreign_keys=[user_id])
    engagements = relationship("Engagement", back_populates="professional", cascade="all, delete-orphan")


class Engagement(Base):
    __tablename__ = "engagements"

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
    engagement_type = Column(
        Enum(EngagementType, name="engagement_type_enum", native_enum=False),
        default=EngagementType.contractor,
        nullable=False,
    )
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    contract_status = Column(
        Enum(ContractStatus, name="contract_status_enum", native_enum=False),
        default=ContractStatus.active,
        nullable=False,
    )
    compensation_rate = Column(String(100), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    professional = relationship("Professional", back_populates="engagements")
