"""Safe GitHub mock adapter for DWOP Sprint 0.

The adapter deliberately performs no network I/O. It models GitHub provisioning
semantics in process memory so the access lifecycle can be exercised safely
before a live provider integration is approved.
"""
from __future__ import annotations

import uuid
from typing import Any, ClassVar, Dict, Tuple

from app.integrations.base import BaseProviderAdapter


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

    async def provision_access(self, user_email: str, role_or_scope: str) -> Dict[str, Any]:
        """Simulate granting GitHub access without contacting GitHub.

        ``credentials["simulate_failure"]`` is a mock-only test control used to
        exercise DWOP-012's failure/fallback path. It is never sent externally.
        Repeated provisioning for the same tenant/email is idempotent.
        """
        email = user_email.strip().lower()
        scope = role_or_scope.strip()
        if not email:
            raise ValueError("user_email cannot be empty.")
        if not scope:
            raise ValueError("role_or_scope cannot be empty.")

        if self.credentials.get("simulate_failure"):
            return {
                "provider": self.provider_name,
                "mode": self.mode,
                "tenant_id": self.tenant_id,
                "user_email": email,
                "role_or_scope": scope,
                "status": "failed",
                "external_reference": None,
                "error": "Simulated GitHub provisioning failure.",
            }

        key = self._key(email)
        existing = self._provisioned.get(key)
        if existing is not None:
            return dict(existing)

        record = {
            "provider": self.provider_name,
            "mode": self.mode,
            "tenant_id": self.tenant_id,
            "user_email": email,
            "role_or_scope": scope,
            "status": "provisioned",
            "external_reference": f"gh-mock-{uuid.uuid4()}",
            "error": None,
        }
        self._provisioned[key] = record
        return dict(record)

    async def revoke_access(self, user_email: str) -> bool:
        """Simulate tenant-scoped GitHub access revocation."""
        email = user_email.strip().lower()
        if not email:
            raise ValueError("user_email cannot be empty.")
        if self.credentials.get("simulate_revoke_failure"):
            return False
        return self._provisioned.pop(self._key(email), None) is not None

    async def get_status(self) -> Dict[str, Any]:
        """Return deterministic sandbox health information."""
        return {
            "provider": self.provider_name,
            "tenant_id": self.tenant_id,
            "connection_status": "connected",
            "health_status": "healthy",
            "mode": self.mode,
            "network_io": False,
        }
