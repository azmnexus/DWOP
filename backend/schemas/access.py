from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.access import AccessRequestStatus, AccessType, ApprovalOutcome


class IntegrationCreate(BaseModel):
    provider: str = Field(default="github", max_length=50)
    name: str = Field(default="default", max_length=255)
    auth_type: str = Field(default="oauth2", max_length=50)
    connection_status: str = Field(default="disconnected", max_length=50)
    health_status: str = Field(default="unknown", max_length=50)
    credentials_encrypted: dict | None = None
    scopes: list | None = None
    config: dict | None = None


class IntegrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    provider: str
    name: str
    auth_type: str
    connection_status: str
    health_status: str
    credentials_encrypted: dict | None = None
    scopes: list | None = None
    config: dict | None = None
    created_at: datetime
    updated_at: datetime


class AccessRequestBase(BaseModel):
    professional_id: uuid.UUID
    integration_id: uuid.UUID
    access_type: AccessType = AccessType.generic
    role_or_scope: str = Field(..., max_length=255)
    status: AccessRequestStatus = AccessRequestStatus.requested


class AccessRequestCreate(AccessRequestBase):
    pass


class AccessRequestRead(AccessRequestBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    requested_by_user_id: uuid.UUID
    approved_by_user_id: uuid.UUID | None = None
    requested_at: datetime
    provisioned_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AccessTransitionRequest(BaseModel):
    target_status: AccessRequestStatus
    rationale: str | None = Field(default=None, max_length=1000)


class ApprovalDecisionBase(BaseModel):
    request_type: str = Field(..., max_length=50)
    request_id: uuid.UUID
    outcome: ApprovalOutcome
    rationale: str | None = Field(default=None, max_length=1000)


class ApprovalDecisionCreate(ApprovalDecisionBase):
    pass


class ApprovalDecisionRead(ApprovalDecisionBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    approver_user_id: uuid.UUID
    decided_at: datetime
    created_at: datetime
