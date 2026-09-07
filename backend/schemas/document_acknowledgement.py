from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class DocumentAcknowledgementCreate(BaseModel):
    professional_id: uuid.UUID
    document_title: str = Field(..., max_length=255)
    version: str = Field(default="v1.0", max_length=50)

class DocumentAcknowledgementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    professional_id: uuid.UUID
    document_title: str
    version: str
    status: str
    acknowledged_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
