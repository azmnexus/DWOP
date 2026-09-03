import uuid
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.talent import (
    ProfessionalStatus,
    AvailabilityStatus,
    EngagementType,
    ContractStatus,
)


# ---------------- Engagement Schemas ----------------
class EngagementBase(BaseModel):
    engagement_type: EngagementType = EngagementType.contractor
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    contract_status: ContractStatus = ContractStatus.active
    compensation_rate: Optional[str] = None


class EngagementCreate(EngagementBase):
    pass


class EngagementRead(EngagementBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    professional_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


# ---------------- Professional Schemas ----------------
class ProfessionalBase(BaseModel):
    first_name: str = Field(..., max_length=100, examples=["Jane"])
    last_name: str = Field(..., max_length=100, examples=["Doe"])
    email: EmailStr = Field(..., examples=["jane.doe@azm-nexus.com"])
    phone: Optional[str] = Field(None, max_length=50, examples=["+234 800 123 4567"])
    status: ProfessionalStatus = ProfessionalStatus.intake
    availability_status: AvailabilityStatus = AvailabilityStatus.available
    skills: List[str] = Field(default_factory=list, examples=[["FastAPI", "PostgreSQL", "Docker"]])


class ProfessionalCreate(ProfessionalBase):
    user_id: Optional[uuid.UUID] = None
    engagement: Optional[EngagementCreate] = None


class ProfessionalUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: Optional[ProfessionalStatus] = None
    availability_status: Optional[AvailabilityStatus] = None
    skills: Optional[List[str]] = None
    user_id: Optional[uuid.UUID] = None


class ProfessionalRead(ProfessionalBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    created_at: datetime
    engagements: List[EngagementRead] = []

    model_config = ConfigDict(from_attributes=True)
