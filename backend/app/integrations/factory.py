"""Provider adapter registry and construction helpers."""
from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Type
from uuid import UUID

from app.integrations.base import BaseProviderAdapter
from app.integrations.github_mock import GitHubMockAdapter
from app.integrations.slack_mock import SlackMockAdapter
if TYPE_CHECKING:
    from app.models.access import Integration, IntegrationProvider

logger = logging.getLogger(__name__)


from app.integrations.exceptions import (
    InvalidAdapterConfigError,
    ProviderAuthenticationError,
    ProviderConnectionTimeoutError,
    ProviderIntegrationError,
    UnsupportedProviderError,
)



class ProviderAdapterFactory:
    """Registry-backed constructor for tenant-scoped provider adapters."""

    _registry: ClassVar[Dict[str, Type[BaseProviderAdapter]]] = {}

    @staticmethod
    def _normalize_provider(provider: IntegrationProvider | str) -> str:
        if isinstance(provider, Enum):
            provider = provider.value
        if not isinstance(provider, str):
            raise InvalidAdapterConfigError("Provider configuration is invalid.")
        normalized = provider.strip().lower()
        if not normalized:
            raise InvalidAdapterConfigError("Provider configuration is invalid.")
        return normalized

    @staticmethod
    def _normalize_tenant_id(tenant_id: str | UUID) -> str:
        if tenant_id is None:
            raise InvalidAdapterConfigError("Tenant configuration is invalid.")
        normalized = str(tenant_id).strip()
        if not normalized:
            raise InvalidAdapterConfigError("Tenant configuration is invalid.")
        return normalized

    @staticmethod
    def _normalize_credentials(credentials: Dict[str, Any] | None) -> Dict[str, Any]:
        if credentials is None:
            return {}
        if not isinstance(credentials, dict):
            raise InvalidAdapterConfigError("Integration credentials configuration is invalid.")
        return dict(credentials)

    @classmethod
    def register_provider(
        cls, provider: IntegrationProvider | str, adapter_cls: Type[BaseProviderAdapter]
    ) -> None:
        """Register an implementation behind the provider adapter contract."""
        normalized = cls._normalize_provider(provider)
        if not isinstance(adapter_cls, type) or not issubclass(adapter_cls, BaseProviderAdapter):
            # Preserve the public error type used by the original registration API.
            raise TypeError("Provider adapters must inherit from BaseProviderAdapter.")
        cls._registry[normalized] = adapter_cls

    @classmethod
    def is_supported(cls, provider: IntegrationProvider | str) -> bool:
        """Return whether an adapter is registered without raising for unknown providers."""
        try:
            return cls._normalize_provider(provider) in cls._registry
        except InvalidAdapterConfigError:
            return False

    @classmethod
    def create_adapter(
        cls,
        provider: IntegrationProvider | str,
        tenant_id: str | UUID,
        credentials: Dict[str, Any] | None = None,
    ) -> BaseProviderAdapter:
        """Construct a tenant-scoped adapter for a registered provider."""
        normalized_provider = cls._normalize_provider(provider)
        normalized_tenant_id = cls._normalize_tenant_id(tenant_id)
        normalized_credentials = cls._normalize_credentials(credentials)
        adapter_cls = cls._registry.get(normalized_provider)
        if adapter_cls is None:
            raise UnsupportedProviderError("Provider adapter is not supported.")
        return adapter_cls(tenant_id=normalized_tenant_id, credentials=normalized_credentials)

    @classmethod
    def create_from_integration(cls, integration: Integration) -> BaseProviderAdapter:
        """Construct an adapter from an active Integration domain object.\n\n        An integration is active only when ``connection_status == "connected"``.\n        Sandbox credentials must be a dictionary; decryption and adapter health checks\n        are intentionally outside factory construction.\n        """
        if integration is None:
            raise InvalidAdapterConfigError("Integration configuration is invalid.")
        if not all(hasattr(integration, field) for field in ("provider", "tenant_id", "credentials_encrypted", "connection_status")):
            raise InvalidAdapterConfigError("Integration configuration is invalid.")
        if integration.connection_status != "connected":
            raise InvalidAdapterConfigError("Integration configuration is inactive.")
        if not isinstance(integration.credentials_encrypted, dict):
            raise InvalidAdapterConfigError("Integration credentials configuration is invalid.")
        adapter = cls.create_adapter(
            integration.provider, integration.tenant_id, integration.credentials_encrypted
        )
        logger.info(
            'Provider adapter constructed for provider=%s tenant_id=%s',
            cls._normalize_provider(integration.provider),
            cls._normalize_tenant_id(integration.tenant_id),
        )
        return adapter


# Sprint 0 deliberately resolves GitHub and Slack to safe mock implementations.
ProviderAdapterFactory.register_provider("github", GitHubMockAdapter)
ProviderAdapterFactory.register_provider("slack", SlackMockAdapter)



def register_provider_adapter(
    name: IntegrationProvider | str, adapter_cls: Type[BaseProviderAdapter]
) -> None:
    """Compatibility wrapper for provider adapter registration."""
    ProviderAdapterFactory.register_provider(name, adapter_cls)


def get_provider_adapter(
    provider: IntegrationProvider | str,
    tenant_id: str | UUID,
    credentials: Dict[str, Any] | None = None,
) -> BaseProviderAdapter:
    """Compatibility wrapper for primitive provider adapter construction."""
    return ProviderAdapterFactory.create_adapter(provider, tenant_id, credentials)
