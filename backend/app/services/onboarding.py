import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

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
    OnboardingRunCreate,
    OnboardingItemUpdate,
)
from app.services.audit import AuditService


class OnboardingService:
    """Domain service for onboarding templates, runs, checklist items, and progress lifecycle."""

    def __init__(self, db: Session):
        self.db = db

    def list_templates(self, tenant_id: uuid.UUID) -> List[OnboardingTemplate]:
        """List all onboarding workflow templates scoped to tenant."""
        return (
            self.db.query(OnboardingTemplate)
            .filter(OnboardingTemplate.tenant_id == tenant_id)
            .all()
        )

    def create_template(
        self, tenant_id: uuid.UUID, payload: OnboardingTemplateCreate
    ) -> OnboardingTemplate:
        """Author a reusable role-based onboarding template and its checklist items."""
        template = OnboardingTemplate(
            tenant_id=tenant_id,
            role_target=payload.role_target,
            title=payload.title,
            description=payload.description,
            version=payload.version,
            is_active=payload.is_active,
        )
        self.db.add(template)
        self.db.flush()

        for idx, item in enumerate(payload.items):
            tmpl_item = ChecklistTemplateItem(
                template_id=template.id,
                title=item.title,
                description=item.description,
                order_index=item.order_index if item.order_index != 0 else idx + 1,
                required_evidence_type=item.required_evidence_type,
                default_due_days=item.default_due_days,
            )
            self.db.add(tmpl_item)

        self.db.commit()
        self.db.refresh(template)
        return template

    def start_onboarding_run(
        self,
        tenant_id: uuid.UUID,
        operator: User,
        payload: OnboardingRunCreate,
        commit: bool = True,
    ) -> OnboardingRun:
        """Apply an onboarding template to a professional to instantiate a live run with calculated due dates."""
        # 1. Validate Professional in tenant
        prof = (
            self.db.query(Professional)
            .filter(
                Professional.id == payload.professional_id,
                Professional.tenant_id == tenant_id,
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
            self.db.query(OnboardingTemplate)
            .filter(
                OnboardingTemplate.id == payload.template_id,
                OnboardingTemplate.tenant_id == tenant_id,
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
            tenant_id=tenant_id,
            professional_id=prof.id,
            template_id=tmpl.id,
            assigned_manager_id=payload.assigned_manager_id or operator.id,
            status="in_progress",
            progress_pct=0,
        )
        self.db.add(run)
        self.db.flush()

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
            self.db.add(run_item)

        # Log immutable audit event for onboarding run instantiation
        AuditService(self.db).log_event(
            tenant_id=tenant_id,
            actor_user_id=operator.id,
            action="onboarding_run.created",
            target_type="OnboardingRun",
            target_id=run.id,
            metadata={
                "professional_id": str(prof.id),
                "template_id": str(tmpl.id),
                "items_count": len(tmpl.items),
            },
            commit=False,
        )

        if commit:
            self.db.commit()
            self.db.refresh(run)
        return run

    def list_onboarding_runs(
        self, tenant_id: uuid.UUID, professional_id: Optional[uuid.UUID] = None
    ) -> List[OnboardingRun]:
        """List onboarding runs scoped to tenant, optionally filtered by professional_id."""
        query = self.db.query(OnboardingRun).filter(OnboardingRun.tenant_id == tenant_id)
        if professional_id:
            query = query.filter(OnboardingRun.professional_id == professional_id)
        return query.all()

    def get_onboarding_run(
        self, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> Optional[OnboardingRun]:
        """Retrieve details and checklist progress for an onboarding run."""
        return (
            self.db.query(OnboardingRun)
            .filter(
                OnboardingRun.id == run_id,
                OnboardingRun.tenant_id == tenant_id,
            )
            .first()
        )

    def update_checklist_item(
        self,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: OnboardingItemUpdate,
        current_user: User,
    ) -> OnboardingItem:
        """Update checklist task status (completed/blocked) with blocker justification or evidence reference."""
        run = self.get_onboarding_run(tenant_id, run_id)
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
            self.db.query(OnboardingItem)
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

        self.db.flush()

        # Recalculate run status and progress percentage
        all_items = (
            self.db.query(OnboardingItem).filter(OnboardingItem.run_id == run.id).all()
        )
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

        # Log immutable audit event for checklist task status change
        AuditService(self.db).log_event(
            tenant_id=tenant_id,
            actor_user_id=current_user.id,
            action="onboarding_item.status_changed",
            target_type="OnboardingItem",
            target_id=item.id,
            metadata={
                "run_id": str(run.id),
                "status": item.status,
                "blocker_reason": item.blocker_reason,
                "progress_pct": run.progress_pct,
            },
            commit=False,
        )

        self.db.commit()
        self.db.refresh(item)
        return item
