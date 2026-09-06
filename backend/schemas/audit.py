from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEventCreate(BaseModel):
    action: str = Field(..., max_length=100, description="e.g., ACCESS_APPROVED, PROFESSIONAL_CREATED")
    target_type: str = Field(..., max_length=100, description="e.g., AccessRequest, OnboardingRun")
    target_id: uuid.UUID
    metadata: dict[str, Any] | None = Field(default_factory=dict, description="JSONB diffs/IP/Agent")


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: uuid.UUID
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_")
    timestamp: datetime
    created_at: datetime
