from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class NotificationCreate(BaseModel):
    recipient_user_id: uuid.UUID
    channel: str = Field(default="in_app", max_length=50)
    title: str = Field(..., max_length=255)
    message: str

class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    recipient_user_id: uuid.UUID
    channel: str
    title: str
    message: str
    status: str
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
