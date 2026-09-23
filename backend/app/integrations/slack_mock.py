"""Safe Slack sandbox mock adapter for DWOP Sprint 0.

The adapter performs no network I/O. It models Slack workspace channel / usergroup
provisioning semantics in process memory so multi-provider adapter conformance
can be exercised safely.
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


class SlackMockAdapter(BaseProviderAdapter):
    """Process-local Slack sandbox implementation of ``BaseProviderAdapter``.

    Provider identity is ``slack``. Network I/O is strictly disabled.
    State is tenant-scoped and kept in-memory for multi-provider testing.
    """

    provider_name = "slack"
    mode = "sandbox_mock"

    _members: ClassVar[Dict[Tuple[str, str], Dict[str, Any]]] = {}

    def _key(self, user_email: str) -> Tuple[str, str]:
        return self.tenant_id, user_email.strip().lower()

    async def provision_access(
        self,
        user_context: Union[Dict[str, Any], str],
        role_or_scope: Optional[str] = None,
        **kwargs: Any,
    ) -> AdapterResult:
        """Simulate inviting a user to a Slack workspace channel/usergroup.

        Per Directive Specification:
            ``provision_access(user_context: dict) -> AdapterResult``

        Accepts user_context dict or positional user_email for backwards compatibility.
        """
        if isinstance(user_context, dict):
            email = (user_context.get("email") or user_context.get("user_email") or "").strip().lower()
            scope = (user_context.get("role") or user_context.get("role_or_scope") or user_context.get("channel") or user_context.get("scope") or "general").strip()
            extra_meta = {k: v for k, v in user_context.items() if k not in ("email", "role")}
        else:
            email = str(user_context).strip().lower()
            scope = (role_or_scope or kwargs.get("role_or_scope") or kwargs.get("channel") or "general").strip()
            extra_meta = kwargs

        if not email:
            raise ValueError("user_email cannot be empty.")
        if not scope:
            raise ValueError("role_or_scope cannot be empty.")

        # Fault injection simulation per review mandate
        if self.credentials.get("simulate_timeout") or (isinstance(user_context, dict) and user_context.get("simulate_timeout")):
            raise ProviderConnectionTimeoutError("Simulated connection timeout to Slack endpoint.")
        if self.credentials.get("simulate_auth_error") or (isinstance(user_context, dict) and user_context.get("simulate_auth_error")):
            raise ProviderAuthenticationError("Simulated Slack token authentication rejection.")

        metadata = {
            "mode": self.mode,
            "tenant_id": self.tenant_id,
            "user_email": email,
            "channel": scope,
            "workspace": self.credentials.get("workspace", "azmnexus-workspace"),
            **extra_meta,
        }

        if self.credentials.get("simulate_failure"):
            return AdapterResult(
                success=False,
                status="failed",
                provider=self.provider_name,
                external_id=None,
                error_message="Simulated Slack provisioning failure.",
                metadata=metadata,
            )

        key = self._key(email)
        existing = self._members.get(key)
        if existing is not None:
            return AdapterResult(
                success=True,
                status="provisioned",
                provider=self.provider_name,
                external_id=existing.get("external_id") or existing.get("external_reference"),
                error_message=None,
                metadata=metadata,
            )

        ext_ref = f"slack-user-{uuid.uuid4().hex[:8]}"
        record = {
            "provider": self.provider_name,
            "mode": self.mode,
            "tenant_id": self.tenant_id,
            "user_email": email,
            "channel": scope,
            "status": "provisioned",
            "external_id": ext_ref,
            "external_reference": ext_ref,
            "error_message": None,
        }
        self._members[key] = record
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
        """Simulate deactivating a user from the Slack workspace.

        Per Directive Specification:
            ``revoke_access(external_id: str) -> AdapterResult``

        Accepts provider external ID handle or user email.
        """
        identifier = str(external_id).strip()
        if not identifier:
            raise ValueError("external_id cannot be empty.")

        # Fault injection simulation per review mandate
        if self.credentials.get("simulate_timeout") or kwargs.get("simulate_timeout"):
            raise ProviderConnectionTimeoutError("Simulated connection timeout to Slack endpoint during revocation.")
        if self.credentials.get("simulate_auth_error") or kwargs.get("simulate_auth_error"):
            raise ProviderAuthenticationError("Simulated Slack token authentication rejection during revocation.")

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
                error_message="Simulated Slack revocation failure.",
                metadata=metadata,
            )

        # Look up by external_id or by email in tenant
        popped = None
        for key, record in list(self._members.items()):
            if key[0] == self.tenant_id:
                if record.get("external_id") == identifier or key[1] == identifier.lower():
                    popped = self._members.pop(key)
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
            error_message="User has no active Slack membership.",
            metadata=metadata,
        )

    async def get_status(self) -> AdapterResult:
        """Return deterministic Slack sandbox health information."""
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
