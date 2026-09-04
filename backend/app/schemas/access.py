import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.access import AccessRequestStatus, AccessType


class AccessRequestCreate(BaseModel):
    professional_id: uuid.UUID
    integration_id: uuid.UUID
    access_type: AccessType
    role_or_scope: str = Field(min_length=1, max_length=255)


class AccessApprovalRequest(BaseModel):
    rationale: Optional[str] = Field(default=None, max_length=1000)


class AccessRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    professional_id: uuid.UUID
    integration_id: uuid.UUID
    access_type: AccessType
    role_or_scope: str
    status: AccessRequestStatus
    requested_by_user_id: uuid.UUID
    approved_by_user_id: Optional[uuid.UUID]
    requested_at: datetime
    provisioned_at: Optional[datetime]


class AccessProvisionResult(BaseModel):
    request: AccessRequestRead
    provider: str
    provider_status: str
    external_reference: Optional[str] = None
    error: Optional[str] = None
