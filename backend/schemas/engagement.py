from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.engagement import ContractStatus, EngagementType


class EngagementBase(BaseModel):
    professional_id: uuid.UUID
    engagement_type: EngagementType = EngagementType.contractor
    start_date: date | None = None
    end_date: date | None = None
    contract_status: ContractStatus = ContractStatus.active
    compensation_rate: str | None = Field(default=None, max_length=100)


class EngagementCreate(EngagementBase):
    pass


class EngagementUpdate(BaseModel):
    engagement_type: EngagementType | None = None
    start_date: date | None = None
    end_date: date | None = None
    contract_status: ContractStatus | None = None
    compensation_rate: str | None = None


class EngagementRead(EngagementBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
