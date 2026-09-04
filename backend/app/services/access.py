from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

from sqlalchemy.orm import Session

from app.integrations import get_provider_adapter
from app.models.access import (
    AccessRequest,
    AccessRequestStatus,
    ApprovalDecision,
    ApprovalOutcome,
    AuditEvent,
    Integration,
)
from app.models.talent import Professional
from app.models.user import User, UserRole


class AccessLifecycleError(ValueError):
    """Raised when an access lifecycle transition is not permitted."""


_ALLOWED_TRANSITIONS = {
    AccessRequestStatus.requested: {AccessRequestStatus.approved},
    AccessRequestStatus.approved: {AccessRequestStatus.provisioning},
    AccessRequestStatus.provisioning: {
        AccessRequestStatus.provisioned,
        AccessRequestStatus.failed,
    },
    AccessRequestStatus.provisioned: {AccessRequestStatus.revoked},
    AccessRequestStatus.failed: set(),
    AccessRequestStatus.revoked: set(),
}


class AccessService:
    """Tenant-scoped, audited access-request lifecycle service."""

    def __init__(self, db: Session):
        self.db = db

    def _request(self, tenant_id: uuid.UUID, request_id: uuid.UUID) -> AccessRequest:
        request = (
            self.db.query(AccessRequest)
            .filter(
                AccessRequest.id == request_id,
                AccessRequest.tenant_id == tenant_id,
            )
            .first()
        )
        if request is None:
            raise LookupError("Access request not found.")
        return request

    def _transition(
        self,
        request: AccessRequest,
        to_status: AccessRequestStatus,
        actor_user_id: uuid.UUID,
        *,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        from_status = request.status
        if to_status not in _ALLOWED_TRANSITIONS[from_status]:
            raise AccessLifecycleError(
                f"Invalid access transition: {from_status.value} -> {to_status.value}."
            )
        request.status = to_status
        self._audit(
            tenant_id=request.tenant_id,
            actor_user_id=actor_user_id,
            action="access_request.status_changed",
            target_id=request.id,
            metadata={
                "before": {"status": from_status.value},
                "after": {"status": to_status.value},
                **(metadata or {}),
            },
        )

    def _audit(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        action: str,
        target_id: uuid.UUID,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action=action,
                target_type="access_request",
                target_id=target_id,
                event_metadata=metadata or {},
            )
        )

    def list_requests(self, current_user: User) -> Iterable[AccessRequest]:
        query = self.db.query(AccessRequest).filter(
            AccessRequest.tenant_id == current_user.tenant_id
        )
        if current_user.role == UserRole.MEMBER:
            professional = (
                self.db.query(Professional)
                .filter(
                    Professional.tenant_id == current_user.tenant_id,
                    Professional.user_id == current_user.id,
                )
                .first()
            )
            if professional is None:
                return []
            query = query.filter(AccessRequest.professional_id == professional.id)
        return query.order_by(AccessRequest.requested_at.desc()).all()

    def get_request_for_user(
        self, current_user: User, request_id: uuid.UUID
    ) -> AccessRequest:
        request = self._request(current_user.tenant_id, request_id)
        if current_user.role == UserRole.MEMBER:
            professional = (
                self.db.query(Professional)
                .filter(
                    Professional.tenant_id == current_user.tenant_id,
                    Professional.user_id == current_user.id,
                    Professional.id == request.professional_id,
                )
                .first()
            )
            if professional is None:
                raise LookupError("Access request not found.")
        return request

    def create_request(
        self,
        *,
        tenant_id: uuid.UUID,
        professional_id: uuid.UUID,
        integration_id: uuid.UUID,
        access_type,
        role_or_scope: str,
        requested_by: User,
    ) -> AccessRequest:
        professional = (
            self.db.query(Professional)
            .filter(
                Professional.id == professional_id,
                Professional.tenant_id == tenant_id,
            )
            .first()
        )
        if professional is None:
            raise LookupError("Professional not found in current tenant.")
        if requested_by.role == UserRole.MEMBER and professional.user_id != requested_by.id:
            raise AccessLifecycleError("Members can request access only for their own professional profile.")

        integration = (
            self.db.query(Integration)
            .filter(
                Integration.id == integration_id,
                Integration.tenant_id == tenant_id,
            )
            .first()
        )
        if integration is None:
            raise LookupError("Integration not found in current tenant.")

        request = AccessRequest(
            tenant_id=tenant_id,
            professional_id=professional_id,
            integration_id=integration_id,
            access_type=access_type,
            role_or_scope=role_or_scope.strip(),
            status=AccessRequestStatus.requested,
            requested_by_user_id=requested_by.id,
        )
        self.db.add(request)
        self.db.flush()
        self._audit(
            tenant_id=tenant_id,
            actor_user_id=requested_by.id,
            action="access_request.created",
            target_id=request.id,
            metadata={"after": {"status": AccessRequestStatus.requested.value}},
        )
        self.db.commit()
        self.db.refresh(request)
        return request

    def approve_request(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: uuid.UUID,
        approver: User,
        rationale: str | None = None,
    ) -> AccessRequest:
        request = self._request(tenant_id, request_id)
        self._transition(request, AccessRequestStatus.approved, approver.id)
        request.approved_by_user_id = approver.id
        self.db.add(
            ApprovalDecision(
                tenant_id=tenant_id,
                request_type="access",
                request_id=request.id,
                approver_user_id=approver.id,
                outcome=ApprovalOutcome.approved,
                rationale=rationale,
            )
        )
        self.db.commit()
        self.db.refresh(request)
        return request

    async def provision_request(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: uuid.UUID,
        actor: User,
    ) -> tuple[AccessRequest, Dict[str, Any]]:
        request = self._request(tenant_id, request_id)
        integration = (
            self.db.query(Integration)
            .filter(
                Integration.id == request.integration_id,
                Integration.tenant_id == tenant_id,
            )
            .first()
        )
        professional = (
            self.db.query(Professional)
            .filter(
                Professional.id == request.professional_id,
                Professional.tenant_id == tenant_id,
            )
            .first()
        )
        if integration is None or professional is None:
            raise LookupError("Access request dependencies are missing.")

        self._transition(request, AccessRequestStatus.provisioning, actor.id)
        self.db.commit()

        try:
            adapter = get_provider_adapter(
                integration.provider.value,
                str(tenant_id),
                dict(integration.credentials_encrypted or {}),
            )
            result = await adapter.provision_access(
                professional.email, request.role_or_scope
            )
        except Exception as exc:
            # Provider failures must never leave the DB-backed lifecycle stuck in
            # ``provisioning``. Persist a controlled failure and keep provider
            # exception details out of the public API response.
            self._transition(
                request,
                AccessRequestStatus.failed,
                actor.id,
                metadata={
                    "provider": integration.provider.value,
                    "error": "Provider adapter raised an exception.",
                },
            )
            self.db.commit()
            self.db.refresh(request)
            return request, {
                "provider": integration.provider.value,
                "status": "failed",
                "external_reference": None,
                "error": "Provider provisioning failed.",
            }

        if result.get("status") == "provisioned":
            self._transition(
                request,
                AccessRequestStatus.provisioned,
                actor.id,
                metadata={"provider": integration.provider.value},
            )
            request.provisioned_at = datetime.now(timezone.utc)
        else:
            self._transition(
                request,
                AccessRequestStatus.failed,
                actor.id,
                metadata={
                    "provider": integration.provider.value,
                    "error": result.get("error"),
                },
            )

        self.db.commit()
        self.db.refresh(request)
        return request, result

    async def revoke_request(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: uuid.UUID,
        actor: User,
    ) -> AccessRequest:
        request = self._request(tenant_id, request_id)
        if request.status != AccessRequestStatus.provisioned:
            raise AccessLifecycleError(
                f"Invalid access transition: {request.status.value} -> revoked."
            )

        integration = (
            self.db.query(Integration)
            .filter(
                Integration.id == request.integration_id,
                Integration.tenant_id == tenant_id,
            )
            .first()
        )
        professional = (
            self.db.query(Professional)
            .filter(
                Professional.id == request.professional_id,
                Professional.tenant_id == tenant_id,
            )
            .first()
        )
        if integration is None or professional is None:
            raise LookupError("Access request dependencies are missing.")

        adapter = get_provider_adapter(
            integration.provider.value,
            str(tenant_id),
            dict(integration.credentials_encrypted or {}),
        )
        try:
            revoked = await adapter.revoke_access(professional.email)
        except Exception:
            revoked = False

        if not revoked:
            self._audit(
                tenant_id=tenant_id,
                actor_user_id=actor.id,
                action="access_request.revocation_failed",
                target_id=request.id,
                metadata={"provider": integration.provider.value},
            )
            self.db.commit()
            raise AccessLifecycleError("Provider revocation failed; request remains provisioned.")

        self._transition(
            request,
            AccessRequestStatus.revoked,
            actor.id,
            metadata={"provider": integration.provider.value},
        )
        self.db.commit()
        self.db.refresh(request)
        return request
