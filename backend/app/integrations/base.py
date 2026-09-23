"""Provider Adapter Pattern package (Oladotun's domain)."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union

from app.integrations.result import AdapterResult


class BaseProviderAdapter(ABC):
    """Abstract interface for third-party provider integrations (GitHub, Trello, Slack)."""

    def __init__(self, tenant_id: str, credentials: Dict[str, Any]):
        self.tenant_id = tenant_id
        self.credentials = credentials

    @abstractmethod
    async def provision_access(
        self,
        user_context: Union[Dict[str, Any], str],
        role_or_scope: Optional[str] = None,
        **kwargs: Any,
    ) -> AdapterResult:
        """Provision access / invite user to provider organization.

        Per Implementation Directive:
            ``provision_access(user_context: dict) -> AdapterResult``

        For backwards compatibility, implementations also accept ``user_email: str``
        as the first positional parameter alongside ``role_or_scope``.
        """
        pass

    @abstractmethod
    async def revoke_access(
        self,
        external_id: str,
        **kwargs: Any,
    ) -> AdapterResult:
        """Revoke user access from provider.

        Per Implementation Directive:
            ``revoke_access(external_id: str) -> AdapterResult``

        Accepts provider external ID handle or user email for revocation.
        """
        pass

    @abstractmethod
    async def get_status(self) -> AdapterResult:
        """Check provider connectivity & quota."""
        pass

