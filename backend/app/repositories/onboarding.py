"""Onboarding repository for workflow templates, checklist definitions, and runs."""
from __future__ import annotations

import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.onboarding import (
    ChecklistTemplateItem,
    OnboardingItem,
    OnboardingRun,
    OnboardingTemplate,
)
from app.repositories.base import BaseRepository


class OnboardingRepository:
    """Domain repository for onboarding blueprints, active runs, and checklist tasks."""

    def __init__(self, db: Session):
        self.db = db
        self.template_repo = BaseRepository[OnboardingTemplate](db, OnboardingTemplate)
        self.run_repo = BaseRepository[OnboardingRun](db, OnboardingRun)

    # ---------------- Template Operations ----------------
    def list_templates(self, tenant_id: uuid.UUID) -> List[OnboardingTemplate]:
        """List all active and inactive templates for tenant."""
        return self.template_repo._scoped_query(tenant_id).all()

    def get_template(
        self, tenant_id: uuid.UUID, template_id: uuid.UUID
    ) -> Optional[OnboardingTemplate]:
        """Fetch template strictly scoped to tenant."""
        return self.template_repo.get_by_id(tenant_id, template_id)

    def create_template(
        self,
        template: OnboardingTemplate,
        items: List[ChecklistTemplateItem],
    ) -> OnboardingTemplate:
        """Stage an onboarding blueprint and its template checklist items. Flushes without committing."""
        self.db.add(template)
        self.db.flush()
        for item in items:
            item.template_id = template.id
            self.db.add(item)
        self.db.flush()
        return template

    # ---------------- Run Operations ----------------
    def get_run(
        self, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> Optional[OnboardingRun]:
        """Fetch an active or historical onboarding run scoped to tenant."""
        return self.run_repo.get_by_id(tenant_id, run_id)

    def get_run_by_professional(
        self, tenant_id: uuid.UUID, professional_id: uuid.UUID
    ) -> Optional[OnboardingRun]:
        """Fetch the most recent onboarding run for a professional in tenant."""
        return (
            self.run_repo._scoped_query(tenant_id)
            .filter(OnboardingRun.professional_id == professional_id)
            .order_by(OnboardingRun.created_at.desc())
            .first()
        )

    def list_runs(
        self,
        tenant_id: uuid.UUID,
        professional_id: Optional[uuid.UUID] = None,
    ) -> List[OnboardingRun]:
        """List onboarding runs scoped to tenant, optionally filtered by talent."""
        query = self.run_repo._scoped_query(tenant_id)
        if professional_id:
            query = query.filter(OnboardingRun.professional_id == professional_id)
        return query.order_by(OnboardingRun.created_at.desc()).all()

    def create_run(
        self,
        run: OnboardingRun,
        items: List[OnboardingItem],
    ) -> OnboardingRun:
        """Stage an instantiated onboarding run and its concrete checklist items. Flushes without committing."""
        self.db.add(run)
        self.db.flush()
        for item in items:
            item.run_id = run.id
            self.db.add(item)
        self.db.flush()
        return run

    def get_item(
        self, tenant_id: uuid.UUID, run_id: uuid.UUID, item_id: uuid.UUID
    ) -> Optional[OnboardingItem]:
        """Fetch a specific checklist item verifying tenant ownership of the parent run."""
        return (
            self.db.query(OnboardingItem)
            .join(OnboardingRun, OnboardingItem.run_id == OnboardingRun.id)
            .filter(
                OnboardingRun.tenant_id == tenant_id,
                OnboardingRun.id == run_id,
                OnboardingItem.id == item_id,
            )
            .first()
        )

    def list_items_for_run(self, run_id: uuid.UUID) -> List[OnboardingItem]:
        """Fetch all concrete checklist items for a given run."""
        return (
            self.db.query(OnboardingItem)
            .filter(OnboardingItem.run_id == run_id)
            .all()
        )

    def has_manager_assignment(
        self, tenant_id: uuid.UUID, manager_user_id: uuid.UUID, professional_id: uuid.UUID
    ) -> bool:
        """Check whether a manager is assigned to an onboarding run for the professional."""
        return (
            self.run_repo._scoped_query(tenant_id)
            .filter(
                OnboardingRun.professional_id == professional_id,
                OnboardingRun.assigned_manager_id == manager_user_id,
            )
            .first()
            is not None
        )
