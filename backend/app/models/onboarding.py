import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, Text, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class OnboardingTemplate(Base):
    __tablename__ = "onboarding_templates"

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
    role_target = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    items = relationship(
        "ChecklistTemplateItem",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ChecklistTemplateItem.order_index",
    )
    runs = relationship("OnboardingRun", back_populates="template")


class ChecklistTemplateItem(Base):
    __tablename__ = "checklist_template_items"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0, nullable=False)
    required_evidence_type = Column(String(50), default="none", nullable=False)
    default_due_days = Column(Integer, default=3, nullable=False)

    # Relationships
    template = relationship("OnboardingTemplate", back_populates="items")


class OnboardingRun(Base):
    __tablename__ = "onboarding_runs"

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
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_manager_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(String(50), default="in_progress", nullable=False)  # in_progress, blocked, completed
    progress_pct = Column(Integer, default=0, nullable=False)
    started_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    professional = relationship("Professional")
    template = relationship("OnboardingTemplate", back_populates="runs")
    assigned_manager = relationship("User", foreign_keys=[assigned_manager_id])
    items = relationship(
        "OnboardingItem",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="OnboardingItem.due_date",
    )


class OnboardingItem(Base):
    __tablename__ = "onboarding_items"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    owner_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(String(50), default="pending", nullable=False)  # pending, blocked, completed
    due_date = Column(Date, nullable=True)
    blocker_reason = Column(Text, nullable=True)
    evidence_ref = Column(String(500), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    run = relationship("OnboardingRun", back_populates="items")
    owner = relationship("User", foreign_keys=[owner_user_id])
