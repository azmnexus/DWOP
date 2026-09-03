import uuid
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# ---------------- Checklist Template Item Schemas ----------------
class ChecklistTemplateItemBase(BaseModel):
    title: str = Field(..., max_length=255, examples=["Sign Confidentiality & Non-Disclosure Agreement (NDA)"])
    description: Optional[str] = None
    order_index: int = 0
    required_evidence_type: str = Field("none", max_length=50, examples=["signed_pdf"])
    default_due_days: int = Field(3, examples=[1])


class ChecklistTemplateItemCreate(ChecklistTemplateItemBase):
    pass


class ChecklistTemplateItemRead(ChecklistTemplateItemBase):
    id: uuid.UUID
    template_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


# ---------------- Onboarding Template Schemas ----------------
class OnboardingTemplateBase(BaseModel):
    role_target: str = Field(..., max_length=100, examples=["Software Engineer"])
    title: str = Field(..., max_length=255, examples=["Standard Software Engineer Onboarding v2.1"])
    description: Optional[str] = None
    version: int = 1
    is_active: bool = True


class OnboardingTemplateCreate(OnboardingTemplateBase):
    items: List[ChecklistTemplateItemCreate] = Field(default_factory=list)


class OnboardingTemplateRead(OnboardingTemplateBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    items: List[ChecklistTemplateItemRead] = []

    model_config = ConfigDict(from_attributes=True)


# ---------------- Onboarding Item Schemas ----------------
class OnboardingItemBase(BaseModel):
    title: str
    owner_user_id: Optional[uuid.UUID] = None
    status: str = "pending"  # pending, blocked, completed
    due_date: Optional[date] = None
    blocker_reason: Optional[str] = None
    evidence_ref: Optional[str] = None


class OnboardingItemUpdate(BaseModel):
    status: Optional[str] = Field(None, examples=["completed", "blocked"])
    blocker_reason: Optional[str] = Field(None, examples=["Awaiting corporate 2FA hardware token"])
    evidence_ref: Optional[str] = Field(None, examples=["https://storage.azm.nexus/evidence/nda_signed.pdf"])


class OnboardingItemRead(OnboardingItemBase):
    id: uuid.UUID
    run_id: uuid.UUID
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------- Onboarding Run Schemas ----------------
class OnboardingRunCreate(BaseModel):
    professional_id: uuid.UUID
    template_id: uuid.UUID
    assigned_manager_id: Optional[uuid.UUID] = None


class OnboardingRunRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    professional_id: uuid.UUID
    template_id: uuid.UUID
    assigned_manager_id: Optional[uuid.UUID] = None
    status: str
    progress_pct: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    items: List[OnboardingItemRead] = []

    model_config = ConfigDict(from_attributes=True)
