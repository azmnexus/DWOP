from __future__ import annotations

import uuid
from datetime import date, timedelta, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.onboarding import (
    ChecklistTemplateItem,
    OnboardingItem,
    OnboardingItemStatus,
    OnboardingRun,
    OnboardingRunStatus,
    OnboardingTemplate,
)
from backend.models.professional import Professional
from backend.models.user import User
from backend.services.base import TenantScopedService


class OnboardingTemplateService(TenantScopedService[OnboardingTemplate]):
    def __init__(self, db: AsyncSession):
        super().__init__(OnboardingTemplate, db)


class ChecklistTemplateItemService(TenantScopedService[ChecklistTemplateItem]):
    def __init__(self, db: AsyncSession):
        super().__init__(ChecklistTemplateItem, db)

    async def create(self, data: dict, tenant_id: uuid.UUID | None = None) -> ChecklistTemplateItem:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        # Validate template belongs to tenant
        template_id = data.get("template_id")
        if template_id:
            t = await self.db.execute(select(OnboardingTemplate).where(OnboardingTemplate.id == template_id, OnboardingTemplate.tenant_id == tid))
            if not t.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="template_id not found in tenant")
        # Checklist items inherit tenant via template, but we also store via template FK only;
        # enforce tenant scoping via join on list/get
        obj = ChecklistTemplateItem(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def list_for_template(self, template_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> list[ChecklistTemplateItem]:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        # ensure template scoped
        t = await self.db.execute(select(OnboardingTemplate).where(OnboardingTemplate.id == template_id, OnboardingTemplate.tenant_id == tid))
        if not t.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Template not found")
        result = await self.db.execute(
            select(ChecklistTemplateItem).where(ChecklistTemplateItem.template_id == template_id).order_by(ChecklistTemplateItem.order_index)
        )
        return list(result.scalars().all())


class OnboardingService:
    """
    Core blueprint instantiation + run lifecycle logic.
    - instantiate_onboarding_run(): creates run + copies checklist items atomically
    - update progress_pct, auto-complete detection, blocking
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def instantiate_onboarding_run(
        self, professional_id: uuid.UUID, template_id: uuid.UUID, assigned_manager_id: uuid.UUID | None = None, tenant_id: uuid.UUID | None = None
    ) -> OnboardingRun:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()

        # Validate professional and template belong to tenant
        prof = await self.db.execute(select(Professional).where(Professional.id == professional_id, Professional.tenant_id == tid))
        if not prof.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="professional_id not found in tenant")

        tmpl = await self.db.execute(select(OnboardingTemplate).where(OnboardingTemplate.id == template_id, OnboardingTemplate.tenant_id == tid))
        template = tmpl.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=400, detail="template_id not found in tenant or inactive")
        if not template.is_active:
            raise HTTPException(status_code=400, detail="Template is inactive")

        if assigned_manager_id:
            mgr = await self.db.execute(select(User).where(User.id == assigned_manager_id, User.tenant_id == tid))
            if not mgr.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="assigned_manager_id not found in tenant")

        # Load checklist items ordered
        items_result = await self.db.execute(
            select(ChecklistTemplateItem).where(ChecklistTemplateItem.template_id == template_id).order_by(ChecklistTemplateItem.order_index)
        )
        checklist_items = list(items_result.scalars().all())
        if not checklist_items:
            raise HTTPException(status_code=400, detail="Template has no checklist items to instantiate")

        # Create run
        run = OnboardingRun(
            tenant_id=tid,
            professional_id=professional_id,
            template_id=template_id,
            assigned_manager_id=assigned_manager_id,
            status=OnboardingRunStatus.in_progress,
            progress_pct=0,
        )
        self.db.add(run)
        await self.db.flush()  # get run.id

        # Auto-generate child items copying definitions
        today = date.today()
        for tmpl_item in checklist_items:
            due = today + timedelta(days=tmpl_item.default_due_days) if tmpl_item.default_due_days else None
            item = OnboardingItem(
                tenant_id=tid,
                run_id=run.id,
                title=tmpl_item.title,
                owner_user_id=assigned_manager_id,  # default owner is manager; can be reassigned later
                status=OnboardingItemStatus.pending,
                due_date=due,
                blocker_reason=None,
                evidence_ref=None,
            )
            self.db.add(item)

        await self.db.flush()
        await self.db.refresh(run)
        # progress recalc (0% initially)
        await self.recalc_progress(run.id, tenant_id=tid)
        # === Auto-Audit ===
        from backend.services.audit_helpers import emit_audit, emit_notification

        await emit_audit(
            self.db,
            action="ONBOARDING_RUN_CREATED",
            target_type="OnboardingRun",
            target_id=run.id,
            actor_user_id=assigned_manager_id,
            tenant_id=tid,
            metadata={"professional_id": str(professional_id), "template_id": str(template_id), "items_count": len(checklist_items)},
        )
        # === Notification: notify the assigned manager ===
        if assigned_manager_id:
            await emit_notification(
                self.db,
                tenant_id=tid,
                recipient_user_id=assigned_manager_id,
                title="New Onboarding Run Assigned",
                message=f"An onboarding run has been created and assigned to you. Run ID: {run.id}. Professional ID: {professional_id}.",
            )
        return run

    async def recalc_progress(self, run_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> OnboardingRun:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        run_result = await self.db.execute(select(OnboardingRun).where(OnboardingRun.id == run_id, OnboardingRun.tenant_id == tid))
        run = run_result.scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail="OnboardingRun not found")

        total = await self.db.execute(select(func.count()).select_from(OnboardingItem).where(OnboardingItem.run_id == run_id, OnboardingItem.tenant_id == tid))
        total_count = total.scalar_one()
        if total_count == 0:
            run.progress_pct = 0
        else:
            completed = await self.db.execute(
                select(func.count()).select_from(OnboardingItem).where(OnboardingItem.run_id == run_id, OnboardingItem.tenant_id == tid, OnboardingItem.status == OnboardingItemStatus.completed)
            )
            completed_count = completed.scalar_one()
            run.progress_pct = int((completed_count / total_count) * 100)
            # Auto status transitions
            blocked_items = await self.db.execute(
                select(func.count()).select_from(OnboardingItem).where(OnboardingItem.run_id == run_id, OnboardingItem.tenant_id == tid, OnboardingItem.status == OnboardingItemStatus.blocked)
            )
            blocked_count = blocked_items.scalar_one()
            if run.progress_pct == 100:
                run.status = OnboardingRunStatus.completed
                run.completed_at = datetime.now(timezone.utc)
            elif blocked_count > 0:
                run.status = OnboardingRunStatus.blocked
            else:
                run.status = OnboardingRunStatus.in_progress
                run.completed_at = None

        await self.db.flush()
        await self.db.refresh(run)
        return run

    async def update_item_status(
        self, item_id: uuid.UUID, status: OnboardingItemStatus, tenant_id: uuid.UUID | None = None, **extra
    ) -> OnboardingItem:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        result = await self.db.execute(select(OnboardingItem).where(OnboardingItem.id == item_id, OnboardingItem.tenant_id == tid))
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="OnboardingItem not found")
        item.status = status
        for k, v in extra.items():
            if hasattr(item, k) and v is not None:
                setattr(item, k, v)
        if status == OnboardingItemStatus.completed:
            item.completed_at = datetime.now(timezone.utc)
            item.blocker_reason = None
        elif status == OnboardingItemStatus.blocked and not extra.get("blocker_reason"):
            raise HTTPException(status_code=400, detail="blocker_reason required when status=blocked")
        await self.db.flush()
        await self.recalc_progress(item.run_id, tenant_id=tid)
        # === Auto-Audit ===
        from backend.services.audit_helpers import emit_audit, emit_notification

        await emit_audit(
            self.db,
            action=f"ONBOARDING_ITEM_{status.value.upper()}",
            target_type="OnboardingItem",
            target_id=item.id,
            tenant_id=tid,
            metadata={"new_status": status.value, "blocker_reason": extra.get("blocker_reason")},
        )
        # === Notification: notify owner when item is blocked ===
        if status == OnboardingItemStatus.blocked and item.owner_user_id:
            await emit_notification(
                self.db,
                tenant_id=tid,
                recipient_user_id=item.owner_user_id,
                title="Onboarding Item Blocked",
                message=f"Item '{item.title}' is blocked. Reason: {extra.get('blocker_reason', 'N/A')}",
            )
        # === Notification: notify owner when run completes (100%) ===
        run_result = await self.db.execute(select(OnboardingRun).where(OnboardingRun.id == item.run_id, OnboardingRun.tenant_id == tid))
        updated_run = run_result.scalar_one_or_none()
        if updated_run and updated_run.status == OnboardingRunStatus.completed and updated_run.assigned_manager_id:
            await emit_notification(
                self.db,
                tenant_id=tid,
                recipient_user_id=updated_run.assigned_manager_id,
                title="Onboarding Complete",
                message=f"All checklist items for onboarding run {updated_run.id} are now complete (100%).",
            )
        await self.db.refresh(item)
        return item
