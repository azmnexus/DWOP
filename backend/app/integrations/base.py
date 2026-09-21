"""Provider Adapter Pattern package (Oladotun's domain)."""
from abc import ABC, abstractmethod
from typing import Any, Dict

from app.integrations.result import AdapterResult


class BaseProviderAdapter(ABC):
    """Abstract interface for third-party provider integrations (GitHub, Trello, Slack)."""

    def __init__(self, tenant_id: str, credentials: Dict[str, Any]):
        self.tenant_id = tenant_id
        self.credentials = credentials

    @abstractmethod
    async def provision_access(self, user_email: str, role_or_scope: str) -> AdapterResult:
        """Provision access / invite user to provider organization."""
        pass

    @abstractmethod
    async def revoke_access(self, user_email: str) -> AdapterResult:
        """Revoke user access from provider."""
        pass

    @abstractmethod
    async def get_status(self) -> AdapterResult:
        """Check provider connectivity & quota."""
        pass

