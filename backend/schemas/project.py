from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.project import ProjectStatus


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Z0-9_-]+$")
    client_id: uuid.UUID
    status: ProjectStatus = ProjectStatus.PLANNING
    start_date: date | None = None
    target_end_date: date | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, pattern=r"^[A-Z0-9_-]+$")
    client_id: uuid.UUID | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    target_end_date: date | None = None


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
