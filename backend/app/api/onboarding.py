import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import (
    get_current_active_user,
    require_admin,
    require_admin_or_manager,
)
from app.models.user import User, UserRole
from app.models.talent import Professional, ProfessionalStatus
from app.models.onboarding import (
    OnboardingTemplate,
    ChecklistTemplateItem,
    OnboardingRun,
    OnboardingItem,
)
from app.schemas.onboarding import (
    OnboardingTemplateCreate,
    OnboardingTemplateRead,
    OnboardingRunCreate,
    OnboardingRunRead,
    OnboardingItemUpdate,
    OnboardingItemRead,
)

router = APIRouter(prefix="/onboarding", tags=["Onboarding Engine"])


# ---------------- Template Management ----------------
@router.get("/templates", response_model=List[OnboardingTemplateRead])
def list_templates(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all onboarding workflow templates scoped to tenant (Accessible by all members)."""
    return (
        db.query(OnboardingTemplate)
        .filter(OnboardingTemplate.tenant_id == current_user.tenant_id)
        .all()
    )


@router.post("/templates", response_model=OnboardingTemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: OnboardingTemplateCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Author a reusable role-based onboarding template and its checklist items (Requires ADMIN role)."""
    template = OnboardingTemplate(
        tenant_id=admin_user.tenant_id,
        role_target=payload.role_target,
        title=payload.title,
        description=payload.description,
        version=payload.version,
        is_active=payload.is_active,
    )
    db.add(template)
    db.flush()

    for idx, item in enumerate(payload.items):
        tmpl_item = ChecklistTemplateItem(
            template_id=template.id,
            title=item.title,
            description=item.description,
            order_index=item.order_index if item.order_index != 0 else idx + 1,
            required_evidence_type=item.required_evidence_type,
            default_due_days=item.default_due_days,
        )
        db.add(tmpl_item)

    db.commit()
    db.refresh(template)
    return template


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
    # 1. Validate Professional in tenant
    prof = (
        db.query(Professional)
        .filter(
            Professional.id == payload.professional_id,
            Professional.tenant_id == operator.tenant_id,
        )
        .first()
    )
    if not prof:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Professional '{payload.professional_id}' not found in current tenant.",
        )

    # 2. Validate Template in tenant
    tmpl = (
        db.query(OnboardingTemplate)
        .filter(
            OnboardingTemplate.id == payload.template_id,
            OnboardingTemplate.tenant_id == operator.tenant_id,
        )
        .first()
    )
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onboarding Template '{payload.template_id}' not found in current tenant.",
        )

    # 3. Create OnboardingRun
    run = OnboardingRun(
        tenant_id=operator.tenant_id,
        professional_id=prof.id,
        template_id=tmpl.id,
        assigned_manager_id=payload.assigned_manager_id or operator.id,
        status="in_progress",
        progress_pct=0,
    )
    db.add(run)
    db.flush()

    # 4. Advance Professional status to 'onboarding'
    prof.status = ProfessionalStatus.onboarding

    # 5. Auto-generate checklist items based on template items
    today = date.today()
    for item in tmpl.items:
        due = today + timedelta(days=item.default_due_days)
        run_item = OnboardingItem(
            run_id=run.id,
            title=item.title,
            owner_user_id=run.assigned_manager_id,
            status="pending",
            due_date=due,
        )
        db.add(run_item)

    db.commit()
    db.refresh(run)
    return run


@router.get("/runs/{run_id}", response_model=OnboardingRunRead)
def get_onboarding_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieve details and checklist progress for an onboarding run."""
    run = (
        db.query(OnboardingRun)
        .filter(
            OnboardingRun.id == run_id,
            OnboardingRun.tenant_id == current_user.tenant_id,
        )
        .first()
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
    run = (
        db.query(OnboardingRun)
        .filter(
            OnboardingRun.id == run_id,
            OnboardingRun.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onboarding run '{run_id}' not found in current tenant.",
        )

    # Permission check: Admin, Manager, or the linked Professional
    is_admin_or_mgr = current_user.role in (UserRole.ADMIN, UserRole.MANAGER)
    is_assigned_prof = (
        run.professional.user_id is not None
        and run.professional.user_id == current_user.id
    )

    if not (is_admin_or_mgr or is_assigned_prof):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this onboarding checklist item.",
        )

    item = (
        db.query(OnboardingItem)
        .filter(
            OnboardingItem.id == item_id,
            OnboardingItem.run_id == run.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checklist item '{item_id}' not found in run.",
        )

    # Update fields
    if payload.status is not None:
        item.status = payload.status
        if payload.status == "completed":
            item.completed_at = datetime.now(timezone.utc)
        else:
            item.completed_at = None

    if payload.blocker_reason is not None:
        item.blocker_reason = payload.blocker_reason

    if payload.evidence_ref is not None:
        item.evidence_ref = payload.evidence_ref

    db.flush()

    # Recalculate run status and progress percentage
    all_items = db.query(OnboardingItem).filter(OnboardingItem.run_id == run.id).all()
    total_count = len(all_items)
    completed_count = sum(1 for i in all_items if i.status == "completed")
    blocked_count = sum(1 for i in all_items if i.status == "blocked")

    if total_count > 0:
        run.progress_pct = int((completed_count / total_count) * 100)
    else:
        run.progress_pct = 0

    if blocked_count > 0:
        run.status = "blocked"
    elif completed_count == total_count and total_count > 0:
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        # Advance professional to 'ready' state upon full completion
        run.professional.status = ProfessionalStatus.ready
    else:
        run.status = "in_progress"

    db.commit()
    db.refresh(item)
    return item
