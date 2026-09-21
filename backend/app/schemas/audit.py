import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    actor_user_id: Optional[uuid.UUID] = None
    action: str
    target_type: str
    target_id: uuid.UUID
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="event_metadata")
    timestamp: datetime
