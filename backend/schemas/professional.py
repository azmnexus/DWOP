from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.models.professional import AvailabilityStatus, ProfessionalStatus


class ProfessionalBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    status: ProfessionalStatus = ProfessionalStatus.intake
    availability_status: AvailabilityStatus = AvailabilityStatus.available
    skills: list | dict | None = Field(default_factory=list)
    user_id: uuid.UUID | None = None


class ProfessionalCreate(ProfessionalBase):
    pass


class ProfessionalCreateWithEngagement(ProfessionalBase):
    engagement: dict | None = None  # {engagement_type, start_date, end_date, contract_status, compensation_rate}


class ProfessionalUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = None
    status: ProfessionalStatus | None = None
    availability_status: AvailabilityStatus | None = None
    skills: list | dict | None = None
    user_id: uuid.UUID | None = None


class ProfessionalRead(ProfessionalBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    engagements: list = Field(default_factory=list)


class BulkImportRequest(BaseModel):
    professionals: list[ProfessionalCreateWithEngagement] = Field(..., min_length=10, max_length=10, description="Exactly 10 professionals required for bulk import")
