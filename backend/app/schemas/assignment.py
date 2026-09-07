import uuid
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.assignment import AssignmentStatus


class AssignmentBase(BaseModel):
    role_on_project: str = Field(..., min_length=2, max_length=100, description="Functional role on project")
    capacity_percentage: int = Field(..., ge=1, le=100, description="Allocated capacity percentage (1-100)")
    start_date: date
    end_date: Optional[date] = None


class AssignmentCreate(AssignmentBase):
    professional_id: uuid.UUID
    project_id: uuid.UUID
    team_id: Optional[uuid.UUID] = None


class AssignmentUpdate(BaseModel):
    role_on_project: Optional[str] = Field(None, min_length=2, max_length=100)
    capacity_percentage: Optional[int] = Field(None, ge=1, le=100)
    end_date: Optional[date] = None
    status: Optional[AssignmentStatus] = None


class AssignmentRead(AssignmentBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    professional_id: uuid.UUID
    project_id: uuid.UUID
    team_id: Optional[uuid.UUID] = None
    status: AssignmentStatus
    created_at: datetime
    professional_name: Optional[str] = None
    project_name: Optional[str] = None
    project_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProfessionalCapacityRead(BaseModel):
    professional_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    availability_status: str
    total_allocated_capacity_pct: int
    remaining_capacity_pct: int
    active_assignments_count: int
    assignments: List[AssignmentRead] = []

    model_config = ConfigDict(from_attributes=True)


class CapacityOverviewRead(BaseModel):
    total_professionals: int
    available_headcount: int
    partially_booked_headcount: int
    fully_booked_headcount: int
    total_active_allocations: int
    average_utilization_pct: float
