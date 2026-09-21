"""Safe Slack sandbox mock adapter for DWOP Sprint 0.

The adapter performs no network I/O. It models Slack workspace channel / usergroup
provisioning semantics in process memory so multi-provider adapter conformance
can be exercised safely.
"""
from __future__ import annotations

import uuid
from typing import Any, ClassVar, Dict, Tuple

from app.integrations.base import BaseProviderAdapter
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

    async def provision_access(self, user_email: str, role_or_scope: str) -> AdapterResult:
        """Simulate inviting a user to a Slack workspace channel/usergroup."""
        email = user_email.strip().lower()
        scope = role_or_scope.strip()
        if not email:
            raise ValueError("user_email cannot be empty.")
        if not scope:
            raise ValueError("role_or_scope cannot be empty.")

        metadata = {
            "mode": self.mode,
            "tenant_id": self.tenant_id,
            "user_email": email,
            "channel": scope,
            "workspace": self.credentials.get("workspace", "azmnexus-workspace"),
        }

        if self.credentials.get("simulate_failure"):
            return AdapterResult(
                success=False,
                status="failed",
                provider=self.provider_name,
                external_reference=None,
                error="Simulated Slack provisioning failure.",
                metadata=metadata,
            )

        key = self._key(email)
        existing = self._members.get(key)
        if existing is not None:
            return AdapterResult(
                success=True,
                status="provisioned",
                provider=self.provider_name,
                external_reference=existing.get("external_reference"),
                error=None,
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
            "external_reference": ext_ref,
            "error": None,
        }
        self._members[key] = record
        return AdapterResult(
            success=True,
            status="provisioned",
            provider=self.provider_name,
            external_reference=ext_ref,
            error=None,
            metadata=metadata,
        )

    async def revoke_access(self, user_email: str) -> AdapterResult:
        """Simulate deactivating a user from the Slack workspace."""
        email = user_email.strip().lower()
        if not email:
            raise ValueError("user_email cannot be empty.")

        metadata = {
            "mode": self.mode,
            "tenant_id": self.tenant_id,
            "user_email": email,
        }

        if self.credentials.get("simulate_revoke_failure"):
            return AdapterResult(
                success=False,
                status="failed",
                provider=self.provider_name,
                external_reference=None,
                error="Simulated Slack revocation failure.",
                metadata=metadata,
            )

        popped = self._members.pop(self._key(email), None)
        if popped is not None:
            return AdapterResult(
                success=True,
                status="revoked",
                provider=self.provider_name,
                external_reference=popped.get("external_reference"),
                error=None,
                metadata=metadata,
            )

        return AdapterResult(
            success=False,
            status="failed",
            provider=self.provider_name,
            external_reference=None,
            error="User has no active Slack membership.",
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
