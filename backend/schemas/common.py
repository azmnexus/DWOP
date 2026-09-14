from __future__ import annotations

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class UUIDModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class TimestampedModel(UUIDModel):
    created_at: datetime
    updated_at: datetime | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(from_attributes=True)
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20
    pages: int = 1


class MessageResponse(BaseModel):
    message: str
    detail: str | None = None
