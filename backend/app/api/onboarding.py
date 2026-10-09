import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.deps import (
    get_onboarding_service,
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
    service: OnboardingService = Depends(get_onboarding_service),
):
    """List all onboarding workflow templates scoped to tenant (Accessible by all members)."""
    return service.list_templates(tenant_id=current_user.tenant_id)


@router.post("/templates", response_model=OnboardingTemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: OnboardingTemplateCreate,
    admin_user: User = Depends(require_admin),
    service: OnboardingService = Depends(get_onboarding_service),
):
    """Author a reusable role-based onboarding template and its checklist items (Requires ADMIN role)."""
    return service.create_template(
        tenant_id=admin_user.tenant_id, payload=payload
    )


# ---------------- Run Execution ----------------
@router.post("/runs", response_model=OnboardingRunRead, status_code=status.HTTP_201_CREATED)
def start_onboarding_run(
    payload: OnboardingRunCreate,
    operator: User = Depends(require_admin_or_manager),
    service: OnboardingService = Depends(get_onboarding_service),
):
    """Apply an onboarding template to a professional to instantiate a live run with calculated due dates.
    Requires ADMIN or MANAGER role.
    """
    return service.start_onboarding_run(
        tenant_id=operator.tenant_id,
        operator=operator,
        payload=payload,
    )


@router.get("/runs", response_model=List[OnboardingRunRead])
def list_onboarding_runs(
    professional_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_active_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    """List onboarding runs scoped to tenant, optionally filtered by professional_id."""
    return service.list_onboarding_runs(
        tenant_id=current_user.tenant_id, professional_id=professional_id
    )


@router.get("/runs/{run_id}", response_model=OnboardingRunRead)
def get_onboarding_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    """Retrieve details and checklist progress for an onboarding run."""
    run = service.get_onboarding_run(
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
    service: OnboardingService = Depends(get_onboarding_service),
):
    """Update checklist task status (completed/blocked) with blocker justification or evidence reference.
    Guarded by RBAC: Admin, Manager, or the assigned Professional.
    """
    return service.update_checklist_item(
        tenant_id=current_user.tenant_id,
        run_id=run_id,
        item_id=item_id,
        payload=payload,
        current_user=current_user,
    )
