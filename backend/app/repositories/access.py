"""Access repository for integrations, access requests, and approval decisions."""
from __future__ import annotations

import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.access import (
    AccessRequest,
    AccessRequestStatus,
    ApprovalDecision,
    Integration,
    IntegrationProvider,
)
from app.repositories.base import BaseRepository


class AccessRepository:
    """Domain repository for tool access requests, approvals, and integrations."""

    def __init__(self, db: Session):
        self.db = db
        self.request_repo = BaseRepository[AccessRequest](db, AccessRequest)
        self.integration_repo = BaseRepository[Integration](db, Integration)
        self.decision_repo = BaseRepository[ApprovalDecision](db, ApprovalDecision)

    # ---------------- Request Operations ----------------
    def get_request(
        self, tenant_id: uuid.UUID, request_id: uuid.UUID
    ) -> Optional[AccessRequest]:
        """Fetch access request strictly scoped to tenant."""
        return self.request_repo.get_by_id(tenant_id, request_id)

    def list_requests(
        self,
        tenant_id: uuid.UUID,
        professional_id: Optional[uuid.UUID] = None,
        integration_id: Optional[uuid.UUID] = None,
        status: Optional[AccessRequestStatus] = None,
    ) -> List[AccessRequest]:
        """Retrieve access requests matching criteria ordered by newest first."""
        query = self.request_repo._scoped_query(tenant_id)
        if professional_id:
            query = query.filter(AccessRequest.professional_id == professional_id)
        if integration_id:
            query = query.filter(AccessRequest.integration_id == integration_id)
        if status:
            query = query.filter(AccessRequest.status == status)
        return query.order_by(AccessRequest.requested_at.desc()).all()

    def create_request(self, request: AccessRequest) -> AccessRequest:
        """Stage an access request. Flushes without committing."""
        self.db.add(request)
        self.db.flush()
        return request

    # ---------------- Integration Operations ----------------
    def get_integration(
        self, tenant_id: uuid.UUID, integration_id: uuid.UUID
    ) -> Optional[Integration]:
        """Fetch integration configuration strictly scoped to tenant."""
        return self.integration_repo.get_by_id(tenant_id, integration_id)

    def get_integration_by_provider(
        self, tenant_id: uuid.UUID, provider: IntegrationProvider
    ) -> Optional[Integration]:
        """Fetch tenant integration by provider enum."""
        return (
            self.integration_repo._scoped_query(tenant_id)
            .filter(Integration.provider == provider)
            .first()
        )

    # ---------------- Decision Operations ----------------
    def create_decision(self, decision: ApprovalDecision) -> ApprovalDecision:
        """Stage an approval decision. Flushes without committing."""
        self.db.add(decision)
        self.db.flush()
        return decision
