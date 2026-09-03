import uuid
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# ---------------- Department Schemas ----------------
class DepartmentBase(BaseModel):
    name: str = Field(..., max_length=255, examples=["Core Engineering"])
    manager_user_id: Optional[uuid.UUID] = None
    parent_department_id: Optional[uuid.UUID] = None


class DepartmentCreate(DepartmentBase):
    # tenant_id is supplied by request context, never from body
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    manager_user_id: Optional[uuid.UUID] = None
    parent_department_id: Optional[uuid.UUID] = None


class DepartmentRead(DepartmentBase):
    id: uuid.UUID
    tenant_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


# ---------------- Team Schemas ----------------
class TeamBase(BaseModel):
    department_id: uuid.UUID
    name: str = Field(..., max_length=255, examples=["Backend Platform Alpha"])
    team_lead_id: Optional[uuid.UUID] = None


class TeamCreate(TeamBase):
    # tenant_id is supplied by request context, never from body
    pass


class TeamUpdate(BaseModel):
    department_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    team_lead_id: Optional[uuid.UUID] = None


class TeamRead(TeamBase):
    id: uuid.UUID
    tenant_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
