from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.access import (
    AccessRequest,
    AccessRequestStatus,
    ApprovalDecision,
    ApprovalOutcome,
    Integration,
)
from backend.models.professional import Professional
from backend.models.user import User
from backend.services.base import TenantScopedService


# Strict state machine definition - enforced in service layer + validated before any DB write
ALLOWED_TRANSITIONS: dict[AccessRequestStatus, set[AccessRequestStatus]] = {
    AccessRequestStatus.requested: {AccessRequestStatus.approved, AccessRequestStatus.failed},
    AccessRequestStatus.approved: {AccessRequestStatus.provisioning, AccessRequestStatus.failed, AccessRequestStatus.revoked},
    AccessRequestStatus.provisioning: {AccessRequestStatus.provisioned, AccessRequestStatus.failed},
    AccessRequestStatus.provisioned: {AccessRequestStatus.revoked},
    AccessRequestStatus.failed: set(),  # terminal; re-request creates new row
    AccessRequestStatus.revoked: set(),  # terminal
}


class AccessRequestService(TenantScopedService[AccessRequest]):
    def __init__(self, db: AsyncSession):
        super().__init__(AccessRequest, db)

    def _assert_transition(self, current: AccessRequestStatus, target: AccessRequestStatus):
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Illegal transition {current.value} -> {target.value}. Allowed from {current.value}: {[s.value for s in allowed] or ['<terminal>']}",
            )

    async def create(
        self, data: dict, requested_by_user_id: uuid.UUID, tenant_id: uuid.UUID | None = None
    ) -> AccessRequest:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        # Validate FKs in tenant
        for fk_field, model in [
            ("professional_id", Professional),
            ("integration_id", Integration),
        ]:
            val = data.get(fk_field)
            if val:
                res = await self.db.execute(select(model).where(model.id == val, model.tenant_id == tid))
                if not res.scalar_one_or_none():
                    raise HTTPException(status_code=400, detail=f"{fk_field} not found in tenant")
        # requested_by must be in tenant
        u = await self.db.execute(select(User).where(User.id == requested_by_user_id, User.tenant_id == tid))
        if not u.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="requested_by_user_id not found in tenant")

        payload = dict(data)
        payload["tenant_id"] = tid
        payload["requested_by_user_id"] = requested_by_user_id
        payload["status"] = AccessRequestStatus.requested
        payload["requested_at"] = datetime.now(timezone.utc)
        obj = AccessRequest(**payload)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def transition(
        self,
        request_id: uuid.UUID,
        target_status: AccessRequestStatus,
        actor_user_id: uuid.UUID | None = None,
        tenant_id: uuid.UUID | None = None,
        rationale: str | None = None,
    ) -> AccessRequest:
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        result = await self.db.execute(select(AccessRequest).where(AccessRequest.id == request_id, AccessRequest.tenant_id == tid))
        req = result.scalar_one_or_none()
        if not req:
            raise HTTPException(status_code=404, detail="AccessRequest not found")

        self._assert_transition(req.status, target_status)

        # Record approval decision for approved/rejected paths
        if target_status == AccessRequestStatus.approved:
            if not actor_user_id:
                raise HTTPException(status_code=400, detail="approved_by_user_id required for approval")
            # validate approver in tenant
            approver = await self.db.execute(select(User).where(User.id == actor_user_id, User.tenant_id == tid))
            if not approver.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="approver not found in tenant")
            decision = ApprovalDecision(
                tenant_id=tid,
                request_type="access_request",
                request_id=req.id,
                approver_user_id=actor_user_id,
                outcome=ApprovalOutcome.approved,
                rationale=rationale,
                decided_at=datetime.now(timezone.utc),
            )
            self.db.add(decision)
            req.approved_by_user_id = actor_user_id
        elif target_status == AccessRequestStatus.failed and actor_user_id:
            # record rejection if actor provided
            decision = ApprovalDecision(
                tenant_id=tid,
                request_type="access_request",
                request_id=req.id,
                approver_user_id=actor_user_id,
                outcome=ApprovalOutcome.rejected,
                rationale=rationale,
                decided_at=datetime.now(timezone.utc),
            )
            self.db.add(decision)

        req.status = target_status
        if target_status == AccessRequestStatus.provisioned:
            req.provisioned_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(req)
        return req

    async def list_for_professional(self, professional_id: uuid.UUID, tenant_id: uuid.UUID | None = None):
        from backend.core.tenancy import get_tenant_id

        tid = tenant_id or get_tenant_id()
        result = await self.db.execute(select(AccessRequest).where(AccessRequest.professional_id == professional_id, AccessRequest.tenant_id == tid))
        return result.scalars().all()


class ApprovalDecisionService(TenantScopedService[ApprovalDecision]):
    def __init__(self, db: AsyncSession):
        super().__init__(ApprovalDecision, db)
