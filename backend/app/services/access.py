from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.integrations import (
    AdapterResult,
    ProviderAdapterFactory,
    ProviderAuthenticationError,
    ProviderConnectionTimeoutError,
)
from app.models.access import (
    AccessRequest,
    AccessRequestStatus,
    ApprovalDecision,
    ApprovalOutcome,
    AuditEvent,
    Integration,
)
from app.repositories.access import AccessRepository
from app.repositories.onboarding import OnboardingRepository
from app.repositories.professional import ProfessionalRepository
from app.services.audit import AuditService
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

    def __init__(
        self,
        db: Session,
        repo: Optional[AccessRepository] = None,
        professional_repo: Optional[ProfessionalRepository] = None,
        onboarding_repo: Optional[OnboardingRepository] = None,
    ):
        self.db = db
        self.repo = repo or AccessRepository(db)
        self.professional_repo = professional_repo or ProfessionalRepository(db)
        self.onboarding_repo = onboarding_repo or OnboardingRepository(db)

    def _request(self, tenant_id: uuid.UUID, request_id: uuid.UUID) -> AccessRequest:
        request = self.repo.get_request(tenant_id, request_id)
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
        AuditService(self.db).log_event(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type="access_request",
            target_id=target_id,
            metadata=metadata or {},
            commit=False,
        )

    def list_requests(self, current_user: User) -> Iterable[AccessRequest]:
        if current_user.role == UserRole.MEMBER:
            professional = self.professional_repo.get_by_user_id(
                current_user.tenant_id, current_user.id
            )
            if professional is None:
                return []
            return self.repo.list_requests(
                current_user.tenant_id, professional_id=professional.id
            )
        return self.repo.list_requests(current_user.tenant_id)

    def get_request_for_user(
        self, current_user: User, request_id: uuid.UUID
    ) -> AccessRequest:
        request = self._request(current_user.tenant_id, request_id)
        if current_user.role == UserRole.MEMBER:
            professional = self.professional_repo.get_by_user_id(
                current_user.tenant_id, current_user.id
            )
            if professional is None or professional.id != request.professional_id:
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
        professional = self.professional_repo.get_by_id(tenant_id, professional_id)
        if professional is None:
            raise LookupError("Professional not found in current tenant.")
        if requested_by.role == UserRole.MEMBER and professional.user_id != requested_by.id:
            raise AccessLifecycleError("Members can request access only for their own professional profile.")

        integration = self.repo.get_integration(tenant_id, integration_id)
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
        self.repo.create_request(request)
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

    def _is_manager_for_professional(
        self, tenant_id: uuid.UUID, manager_user_id: uuid.UUID, professional_id: uuid.UUID
    ) -> bool:
        """Verify if manager supervises this professional via an active onboarding run."""
        return self.onboarding_repo.has_manager_assignment(
            tenant_id=tenant_id,
            manager_user_id=manager_user_id,
            professional_id=professional_id,
        )

    def approve_request(
        self,
        *,
        tenant_id: uuid.UUID,
        request_id: uuid.UUID,
        approver: User,
        rationale: str | None = None,
    ) -> AccessRequest:
        request = self._request(tenant_id, request_id)

        # Locked RBAC Rule: ADMIN has global approval; MANAGER is restricted to direct reports
        if approver.role == UserRole.MANAGER:
            if not self._is_manager_for_professional(tenant_id, approver.id, request.professional_id):
                raise AccessLifecycleError(
                    "Managers are only authorized to approve access requests for direct reports or assigned team members."
                )

        self._transition(request, AccessRequestStatus.approved, approver.id)
        request.approved_by_user_id = approver.id
        self.repo.create_decision(
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
        integration = self.repo.get_integration(tenant_id, request.integration_id)
        professional = self.professional_repo.get_by_id(tenant_id, request.professional_id)
        if integration is None or professional is None:
            raise LookupError("Access request dependencies are missing.")

        self._transition(request, AccessRequestStatus.provisioning, actor.id)
        self.db.commit()

        try:
            adapter = ProviderAdapterFactory.create_from_integration(integration)
            user_context = {
                "email": professional.email,
                "role": request.role_or_scope,
                "professional_id": str(professional.id),
                "tenant_id": str(tenant_id),
            }
            result = await adapter.provision_access(user_context)
        except (ProviderConnectionTimeoutError, ProviderAuthenticationError) as exc:
            self._transition(
                request,
                AccessRequestStatus.failed,
                actor.id,
                metadata={
                    "provider": integration.provider.value,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "error_message": str(exc),
                },
            )
            self.db.commit()
            self.db.refresh(request)
            return request, AdapterResult(
                success=False,
                status="failed",
                provider=integration.provider.value,
                external_id=None,
                error_message=str(exc),
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
                    "error_message": "Provider adapter raised an exception.",
                },
            )
            self.db.commit()
            self.db.refresh(request)
            return request, AdapterResult(
                success=False,
                status="failed",
                provider=integration.provider.value,
                external_id=None,
                error_message="Provider provisioning failed.",
            )

        is_provisioned = (
            result.success
            if isinstance(result, AdapterResult)
            else (result.get("status") == "provisioned")
        )
        provider_name = (
            result.provider
            if isinstance(result, AdapterResult)
            else result.get("provider", integration.provider.value)
        )
        ext_ref = (
            result.external_id
            if isinstance(result, AdapterResult)
            else (result.get("external_id") or result.get("external_reference"))
        )
        error_msg = (
            result.error_message
            if isinstance(result, AdapterResult)
            else (result.get("error_message") or result.get("error"))
        )
        audit_meta = (
            result.to_dict()
            if isinstance(result, AdapterResult)
            else dict(result)
        )

        if is_provisioned:
            self._transition(
                request,
                AccessRequestStatus.provisioned,
                actor.id,
                metadata={
                    "provider": provider_name,
                    "external_id": ext_ref,
                    "external_reference": ext_ref,
                    "adapter_result": audit_meta,
                },
            )
            request.provisioned_at = datetime.now(timezone.utc)
        else:
            self._transition(
                request,
                AccessRequestStatus.failed,
                actor.id,
                metadata={
                    "provider": provider_name,
                    "error": error_msg,
                    "error_message": error_msg,
                    "adapter_result": audit_meta,
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

        integration = self.repo.get_integration(tenant_id, request.integration_id)
        professional = self.professional_repo.get_by_id(tenant_id, request.professional_id)
        if integration is None or professional is None:
            raise LookupError("Access request dependencies are missing.")

        # Determine external identifier: prefer stored external_id in request.metadata, falling back to email
        ext_id = None
        if request.metadata and isinstance(request.metadata, dict):
            ext_id = request.metadata.get("external_id") or request.metadata.get("external_reference")
        if not ext_id:
            ext_id = professional.email

        try:
            adapter = ProviderAdapterFactory.create_from_integration(integration)
            result = await adapter.revoke_access(external_id=ext_id)
            revoked = (
                result.success
                if isinstance(result, AdapterResult)
                else bool(result)
            )
            revocation_meta = (
                result.to_dict()
                if isinstance(result, AdapterResult)
                else {"provider": integration.provider.value}
            )
        except Exception:
            revoked = False
            revocation_meta = {"provider": integration.provider.value}

        if not revoked:
            self._audit(
                tenant_id=tenant_id,
                actor_user_id=actor.id,
                action="access_request.revocation_failed",
                target_id=request.id,
                metadata=revocation_meta,
            )
            self.db.commit()
            raise AccessLifecycleError("Provider revocation failed; request remains provisioned.")

        self._transition(
            request,
            AccessRequestStatus.revoked,
            actor.id,
            metadata=revocation_meta,
        )
        self.db.commit()
        self.db.refresh(request)
        return request

