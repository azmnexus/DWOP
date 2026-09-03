import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class ClientStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    lead = "lead"


class ProjectStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    on_hold = "on_hold"


class Client(Base):
    __tablename__ = "clients"

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
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=True)
    status = Column(
        Enum(ClientStatus, name="client_status_enum", native_enum=False),
        default=ClientStatus.active,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="clients")
    projects = relationship("Project", back_populates="client", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

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
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False, index=True)
    status = Column(
        Enum(ProjectStatus, name="project_status_enum", native_enum=False),
        default=ProjectStatus.active,
        nullable=False,
    )
    start_date = Column(Date, nullable=True)
    target_end_date = Column(Date, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="projects")
    client = relationship("Client", back_populates="projects")
