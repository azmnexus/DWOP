import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class TenantBase(BaseModel):
    name: str = Field(..., max_length=255, examples=["AZM Nexus"])
    slug: str = Field(..., max_length=100, examples=["azm-nexus"])
    domain: Optional[str] = Field(None, max_length=255, examples=["azm-nexus.com"])
    plan_tier: Optional[str] = Field("starter", max_length=50, examples=["enterprise"])
    branding: Optional[Dict[str, Any]] = Field(default_factory=dict)


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    plan_tier: Optional[str] = None
    branding: Optional[Dict[str, Any]] = None


class TenantRead(TenantBase):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
