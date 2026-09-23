"""Safe GitHub mock adapter for DWOP Sprint 0.

The adapter deliberately performs no network I/O. It models GitHub provisioning
semantics in process memory so the access lifecycle can be exercised safely
before a live provider integration is approved.
"""
from __future__ import annotations

import uuid
from typing import Any, ClassVar, Dict, Optional, Tuple, Union

from app.integrations.base import BaseProviderAdapter
from app.integrations.exceptions import (
    ProviderAuthenticationError,
    ProviderConnectionTimeoutError,
)
from app.integrations.result import AdapterResult


class GitHubMockAdapter(BaseProviderAdapter):
    """Process-local GitHub sandbox implementation of ``BaseProviderAdapter``.

    Provider identity remains ``github`` so domain records continue to match the
    DWOP ERD. ``mode=sandbox_mock`` distinguishes this implementation from a
    future live GitHub adapter.

    The class-level store is intentional for Sprint 0: factory calls may create a
    fresh adapter object for each request, while mock provision/revoke operations
    still need to observe the same tenant-scoped sandbox state.
    """

    provider_name = "github"
    mode = "sandbox_mock"

    _provisioned: ClassVar[Dict[Tuple[str, str], Dict[str, Any]]] = {}

    def _key(self, user_email: str) -> Tuple[str, str]:
        return self.tenant_id, user_email.strip().lower()

    async def provision_access(
        self,
        user_context: Union[Dict[str, Any], str],
        role_or_scope: Optional[str] = None,
        **kwargs: Any,
    ) -> AdapterResult:
        """Simulate granting GitHub access without contacting GitHub.

        Per Directive Specification:
            ``provision_access(user_context: dict) -> AdapterResult``

        Accepts a user_context dict (e.g. ``{"email": ..., "role": ...}``)
        or positional ``user_email`` for backwards compatibility.
        """
        if isinstance(user_context, dict):
            email = (user_context.get("email") or user_context.get("user_email") or "").strip().lower()
            scope = (user_context.get("role") or user_context.get("role_or_scope") or user_context.get("scope") or "member").strip()
            extra_meta = {k: v for k, v in user_context.items() if k not in ("email", "role")}
        else:
            email = str(user_context).strip().lower()
            scope = (role_or_scope or kwargs.get("role_or_scope") or "member").strip()
            extra_meta = kwargs

        if not email:
            raise ValueError("user_email cannot be empty.")
        if not scope:
            raise ValueError("role_or_scope cannot be empty.")

        # Fault injection simulation per review mandate
        if self.credentials.get("simulate_timeout") or (isinstance(user_context, dict) and user_context.get("simulate_timeout")):
            raise ProviderConnectionTimeoutError("Simulated connection timeout to GitHub endpoint.")
        if self.credentials.get("simulate_auth_error") or (isinstance(user_context, dict) and user_context.get("simulate_auth_error")):
            raise ProviderAuthenticationError("Simulated GitHub token authentication rejection.")

        metadata = {
            "mode": self.mode,
            "tenant_id": self.tenant_id,
            "user_email": email,
            "role_or_scope": scope,
            **extra_meta,
        }

        if self.credentials.get("simulate_failure"):
            return AdapterResult(
                success=False,
                status="failed",
                provider=self.provider_name,
                external_id=None,
                error_message="Simulated GitHub provisioning failure.",
                metadata=metadata,
            )

        key = self._key(email)
        existing = self._provisioned.get(key)
        if existing is not None:
            return AdapterResult(
                success=True,
                status="provisioned",
                provider=self.provider_name,
                external_id=existing.get("external_id") or existing.get("external_reference"),
                error_message=None,
                metadata=metadata,
            )

        ext_ref = f"gh-mock-{uuid.uuid4()}"
        record = {
            "provider": self.provider_name,
            "mode": self.mode,
            "tenant_id": self.tenant_id,
            "user_email": email,
            "role_or_scope": scope,
            "status": "provisioned",
            "external_id": ext_ref,
            "external_reference": ext_ref,
            "error_message": None,
        }
        self._provisioned[key] = record
        return AdapterResult(
            success=True,
            status="provisioned",
            provider=self.provider_name,
            external_id=ext_ref,
            error_message=None,
            metadata=metadata,
        )

    async def revoke_access(
        self,
        external_id: str,
        **kwargs: Any,
    ) -> AdapterResult:
        """Simulate tenant-scoped GitHub access revocation.

        Per Directive Specification:
            ``revoke_access(external_id: str) -> AdapterResult``

        Accepts provider external ID handle (e.g. ``gh-mock-...``) or user email.
        """
        identifier = str(external_id).strip()
        if not identifier:
            raise ValueError("external_id cannot be empty.")

        # Fault injection simulation per review mandate
        if self.credentials.get("simulate_timeout") or kwargs.get("simulate_timeout"):
            raise ProviderConnectionTimeoutError("Simulated connection timeout to GitHub endpoint during revocation.")
        if self.credentials.get("simulate_auth_error") or kwargs.get("simulate_auth_error"):
            raise ProviderAuthenticationError("Simulated GitHub token authentication rejection during revocation.")

        metadata = {
            "mode": self.mode,
            "tenant_id": self.tenant_id,
            "identifier": identifier,
        }

        if self.credentials.get("simulate_revoke_failure"):
            return AdapterResult(
                success=False,
                status="failed",
                provider=self.provider_name,
                external_id=None,
                error_message="Simulated GitHub revocation failure.",
                metadata=metadata,
            )

        # Look up by external_id or by email in tenant
        popped = None
        for key, record in list(self._provisioned.items()):
            if key[0] == self.tenant_id:
                if record.get("external_id") == identifier or key[1] == identifier.lower():
                    popped = self._provisioned.pop(key)
                    break

        if popped is not None:
            return AdapterResult(
                success=True,
                status="revoked",
                provider=self.provider_name,
                external_id=popped.get("external_id") or popped.get("external_reference"),
                error_message=None,
                metadata=metadata,
            )

        return AdapterResult(
            success=False,
            status="failed",
            provider=self.provider_name,
            external_id=None,
            error_message="User has no provisioned GitHub access.",
            metadata=metadata,
        )

    async def get_status(self) -> AdapterResult:
        """Return deterministic sandbox health information."""
        return AdapterResult(
            success=True,
            status="healthy",
            provider=self.provider_name,
            metadata={
                "tenant_id": self.tenant_id,
                "connection_status": "connected",
                "health_status": "healthy",
                "mode": self.mode,
                "network_io": False,
            },
        )

