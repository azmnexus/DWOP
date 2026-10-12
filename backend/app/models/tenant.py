import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    domain = Column(String(255), nullable=True)
    plan_tier = Column(String(50), default="starter", nullable=False)
    # ADR-002: workspace-level suspension flag. Checked by the single hybrid
    # offboarding-guard query on every authenticated request so a suspended
    # tenant loses access immediately, independent of JWT expiry.
    is_active = Column(Boolean, default=True, server_default="true", nullable=False)
    branding = Column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    departments = relationship("Department", back_populates="tenant", cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="tenant", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="tenant", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="tenant", cascade="all, delete-orphan")
