import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import (
    get_current_active_user,
    require_admin,
    require_admin_or_manager,
)
from app.models.user import User
from app.schemas.onboarding import (
    OnboardingTemplateCreate,
    OnboardingTemplateRead,
    OnboardingRunCreate,
    OnboardingRunRead,
    OnboardingItemUpdate,
    OnboardingItemRead,
)
from app.services.onboarding import OnboardingService

router = APIRouter(prefix="/onboarding", tags=["Onboarding Engine"])


# ---------------- Template Management ----------------
@router.get("/templates", response_model=List[OnboardingTemplateRead])
def list_templates(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all onboarding workflow templates scoped to tenant (Accessible by all members)."""
    return OnboardingService(db).list_templates(tenant_id=current_user.tenant_id)


@router.post("/templates", response_model=OnboardingTemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: OnboardingTemplateCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Author a reusable role-based onboarding template and its checklist items (Requires ADMIN role)."""
    return OnboardingService(db).create_template(
        tenant_id=admin_user.tenant_id, payload=payload
    )


# ---------------- Run Execution ----------------
@router.post("/runs", response_model=OnboardingRunRead, status_code=status.HTTP_201_CREATED)
def start_onboarding_run(
    payload: OnboardingRunCreate,
    operator: User = Depends(require_admin_or_manager),
    db: Session = Depends(get_db),
):
    """Apply an onboarding template to a professional to instantiate a live run with calculated due dates.
    Requires ADMIN or MANAGER role.
    """
    return OnboardingService(db).start_onboarding_run(
        tenant_id=operator.tenant_id,
        operator=operator,
        payload=payload,
    )


@router.get("/runs", response_model=List[OnboardingRunRead])
def list_onboarding_runs(
    professional_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List onboarding runs scoped to tenant, optionally filtered by professional_id."""
    return OnboardingService(db).list_onboarding_runs(
        tenant_id=current_user.tenant_id, professional_id=professional_id
    )


@router.get("/runs/{run_id}", response_model=OnboardingRunRead)
def get_onboarding_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieve details and checklist progress for an onboarding run."""
    run = OnboardingService(db).get_onboarding_run(
        tenant_id=current_user.tenant_id, run_id=run_id
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onboarding run '{run_id}' not found in current tenant.",
        )
    return run


@router.patch("/runs/{run_id}/items/{item_id}", response_model=OnboardingItemRead)
def update_checklist_item(
    run_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: OnboardingItemUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update checklist task status (completed/blocked) with blocker justification or evidence reference.
    Guarded by RBAC: Admin, Manager, or the assigned Professional.
    """
    return OnboardingService(db).update_checklist_item(
        tenant_id=current_user.tenant_id,
        run_id=run_id,
        item_id=item_id,
        payload=payload,
        current_user=current_user,
    )
