from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.onboarding import OnboardingItemStatus, OnboardingRunStatus


class OnboardingTemplateBase(BaseModel):
    role_target: str = Field(..., max_length=100)
    title: str = Field(..., max_length=255)
    description: str | None = None
    version: int = Field(default=1, ge=1)
    is_active: bool = True


class OnboardingTemplateCreate(OnboardingTemplateBase):
    pass


class OnboardingTemplateUpdate(BaseModel):
    role_target: str | None = None
    title: str | None = None
    description: str | None = None
    version: int | None = None
    is_active: bool | None = None


class OnboardingTemplateRead(OnboardingTemplateBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    items: list["ChecklistTemplateItemRead"] = Field(default_factory=list)


class ChecklistTemplateItemBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    order_index: int = Field(default=0, ge=0)
    required_evidence_type: str = Field(default="none", max_length=50)
    default_due_days: int = Field(default=3, ge=0)


class ChecklistTemplateItemCreate(ChecklistTemplateItemBase):
    template_id: uuid.UUID | None = None


class ChecklistTemplateItemRead(ChecklistTemplateItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    template_id: uuid.UUID
    created_at: datetime


class OnboardingRunBase(BaseModel):
    professional_id: uuid.UUID
    template_id: uuid.UUID
    assigned_manager_id: uuid.UUID | None = None
    status: OnboardingRunStatus = OnboardingRunStatus.in_progress
    progress_pct: int = Field(default=0, ge=0, le=100)


class OnboardingRunCreate(BaseModel):
    professional_id: uuid.UUID
    template_id: uuid.UUID
    assigned_manager_id: uuid.UUID | None = None


class OnboardingRunRead(OnboardingRunBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list["OnboardingItemRead"] = Field(default_factory=list)


class OnboardingItemBase(BaseModel):
    title: str = Field(..., max_length=255)
    owner_user_id: uuid.UUID | None = None
    status: OnboardingItemStatus = OnboardingItemStatus.pending
    due_date: date | None = None
    blocker_reason: str | None = None
    evidence_ref: str | None = Field(default=None, max_length=500)


class OnboardingItemUpdate(BaseModel):
    status: OnboardingItemStatus | None = None
    owner_user_id: uuid.UUID | None = None
    due_date: date | None = None
    blocker_reason: str | None = None
    evidence_ref: str | None = None
    completed_at: datetime | None = None


class OnboardingItemRead(OnboardingItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    run_id: uuid.UUID
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
