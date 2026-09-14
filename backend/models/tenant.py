from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class Tenant(Base):
    """
    Root tenant - no tenant_id FK by design (isolation root).
    All other tables reference this.
    """
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    plan_tier: Mapped[str] = mapped_column(String(50), nullable=False, default="free", server_default="free")
    branding: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships (no cascade delete for safety - explicit tenant deletion flow)
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant", lazy="selectin")
    departments: Mapped[list["Department"]] = relationship("Department", back_populates="tenant", lazy="selectin")
    teams: Mapped[list["Team"]] = relationship("Team", back_populates="tenant", lazy="selectin")
    clients: Mapped[list["Client"]] = relationship("Client", back_populates="tenant", lazy="selectin")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="tenant", lazy="selectin")
