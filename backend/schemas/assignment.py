from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.assignment import AssignmentStatus


class AssignmentBase(BaseModel):
    professional_id: uuid.UUID
    project_id: uuid.UUID
    team_id: uuid.UUID | None = None
    role_on_project: str | None = Field(default=None, max_length=100)
    capacity_percentage: int = Field(default=100, ge=1, le=100)
    start_date: date | None = None
    end_date: date | None = None
    status: AssignmentStatus = AssignmentStatus.active


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentUpdate(BaseModel):
    project_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    role_on_project: str | None = None
    capacity_percentage: int | None = Field(default=None, ge=1, le=100)
    start_date: date | None = None
    end_date: date | None = None
    status: AssignmentStatus | None = None


class AssignmentRead(AssignmentBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
