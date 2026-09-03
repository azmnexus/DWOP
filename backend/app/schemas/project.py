import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.project import ClientStatus, ProjectStatus


# ---------------- Client Schemas ----------------
class ClientBase(BaseModel):
    name: str = Field(..., max_length=255, examples=["International Client Corp"])
    contact_email: Optional[EmailStr] = None
    status: ClientStatus = ClientStatus.active


class ClientCreate(ClientBase):
    # tenant_id is supplied by request context, never from body
    pass


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    status: Optional[ClientStatus] = None


class ClientRead(ClientBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------- Project Schemas ----------------
class ProjectBase(BaseModel):
    client_id: Optional[uuid.UUID] = None
    name: str = Field(..., max_length=255, examples=["DWOP Platform MVP"])
    code: str = Field(..., max_length=50, examples=["DWOP-001"])
    status: ProjectStatus = ProjectStatus.active
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None


class ProjectCreate(ProjectBase):
    # tenant_id is supplied by request context, never from body
    pass


class ProjectUpdate(BaseModel):
    client_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    code: Optional[str] = None
    status: Optional[ProjectStatus] = None
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None


class ProjectRead(ProjectBase):
    id: uuid.UUID
    tenant_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
