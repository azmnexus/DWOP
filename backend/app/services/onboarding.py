import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.policy import Permission, policy_engine
from app.core.state_machines import (
    InvalidStateTransitionError,
    OnboardingItemStateMachine,
    OnboardingRunStateMachine,
    TransitionGuardError,
)
from app.models.user import User
from app.models.talent import Professional, ProfessionalStatus
from app.models.onboarding import (
    OnboardingTemplate,
    ChecklistTemplateItem,
    OnboardingRun,
    OnboardingItem,
)
from app.repositories.onboarding import OnboardingRepository
from app.repositories.professional import ProfessionalRepository
from app.schemas.onboarding import (
    OnboardingTemplateCreate,
    OnboardingRunCreate,
    OnboardingItemUpdate,
)
from app.services.audit import AuditService


class OnboardingService:
    """Domain service for onboarding templates, runs, checklist items, and progress lifecycle."""

    def __init__(
        self,
        db: Session,
        repo: Optional[OnboardingRepository] = None,
        professional_repo: Optional[ProfessionalRepository] = None,
        item_state_machine: Optional[OnboardingItemStateMachine] = None,
        run_state_machine: Optional[OnboardingRunStateMachine] = None,
    ):
        self.db = db
        self.repo = repo or OnboardingRepository(db)
        self.professional_repo = professional_repo or ProfessionalRepository(db)
        self.item_state_machine = item_state_machine or OnboardingItemStateMachine()
        self.run_state_machine = run_state_machine or OnboardingRunStateMachine()

    def list_templates(self, tenant_id: uuid.UUID) -> List[OnboardingTemplate]:
        """List all onboarding workflow templates scoped to tenant."""
        return self.repo.list_templates(tenant_id)

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
        items = []
        for idx, item in enumerate(payload.items):
            tmpl_item = ChecklistTemplateItem(
                title=item.title,
                description=item.description,
                order_index=item.order_index if item.order_index != 0 else idx + 1,
                required_evidence_type=item.required_evidence_type,
                default_due_days=item.default_due_days,
            )
            items.append(tmpl_item)

        self.repo.create_template(template, items)
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
        prof = self.professional_repo.get_by_id(tenant_id, payload.professional_id)
        if not prof:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Professional '{payload.professional_id}' not found in current tenant.",
            )

        # 2. Validate Template in tenant
        tmpl = self.repo.get_template(tenant_id, payload.template_id)
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

        # 4. Advance Professional status to 'onboarding'
        prof.status = ProfessionalStatus.onboarding

        # 5. Auto-generate checklist items based on template items
        today = date.today()
        items = []
        for item in tmpl.items:
            due = today + timedelta(days=item.default_due_days)
            run_item = OnboardingItem(
                title=item.title,
                owner_user_id=run.assigned_manager_id,
                status="pending",
                due_date=due,
            )
            items.append(run_item)

        self.repo.create_run(run, items)

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
        return self.repo.list_runs(tenant_id, professional_id)

    def get_onboarding_run(
        self, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> Optional[OnboardingRun]:
        """Retrieve details and checklist progress for an onboarding run."""
        return self.repo.get_run(tenant_id, run_id)

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

        # Permission check resolved in application memory (ADR-002), plus the
        # resource-scoped rule that the linked professional may self-serve.
        can_update_any = policy_engine.has_permission(
            current_user, Permission.ONBOARDING_ITEM_UPDATE_ANY
        )
        can_complete_self = policy_engine.has_permission(
            current_user, Permission.ONBOARDING_ITEM_COMPLETE_SELF
        )
        is_assigned_prof = (
            run.professional.user_id is not None
            and run.professional.user_id == current_user.id
        )

        if not ((can_update_any or can_complete_self) and (can_update_any or is_assigned_prof)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this onboarding checklist item.",
            )

        item = self.repo.get_item(tenant_id, run.id, item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Checklist item '{item_id}' not found in run.",
            )

        # Update fields with state machine validation
        if payload.status is not None:
            effective_blocker_reason = (
                payload.blocker_reason
                if payload.blocker_reason is not None
                else item.blocker_reason
            )
            effective_evidence_ref = (
                payload.evidence_ref
                if payload.evidence_ref is not None
                else item.evidence_ref
            )
            try:
                self.item_state_machine.validate_transition(
                    current_state=item.status,
                    target_state=payload.status,
                    blocker_reason=effective_blocker_reason,
                    evidence_ref=effective_evidence_ref,
                )
            except (InvalidStateTransitionError, TransitionGuardError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc

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
        all_items = self.repo.list_items_for_run(run.id)
        total_count = len(all_items)
        completed_count = sum(1 for i in all_items if i.status == "completed")
        blocked_count = sum(1 for i in all_items if i.status == "blocked")

        if total_count > 0:
            run.progress_pct = int((completed_count / total_count) * 100)
        else:
            run.progress_pct = 0

        target_run_status = "in_progress"
        if blocked_count > 0:
            target_run_status = "blocked"
        elif completed_count == total_count and total_count > 0:
            target_run_status = "completed"

        if target_run_status != run.status:
            try:
                self.run_state_machine.validate_transition(
                    current_state=run.status,
                    target_state=target_run_status,
                    progress_pct=run.progress_pct,
                )
            except (InvalidStateTransitionError, TransitionGuardError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc

            run.status = target_run_status
            if target_run_status == "completed":
                run.completed_at = datetime.now(timezone.utc)
                # Advance professional to 'ready' state upon full completion
                run.professional.status = ProfessionalStatus.ready

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
