"""Provider adapters for external workforce tooling (Oladotun's domain)."""
from app.integrations.base import BaseProviderAdapter
from app.integrations.factory import (
    InvalidAdapterConfigError,
    ProviderAdapterFactory,
    ProviderAuthenticationError,
    ProviderConnectionTimeoutError,
    ProviderIntegrationError,
    UnsupportedProviderError,
    get_provider_adapter,
    register_provider_adapter,
)
from app.integrations.github_mock import GitHubMockAdapter
from app.integrations.result import AdapterResult
from app.integrations.slack_mock import SlackMockAdapter

__all__ = [
    "AdapterResult",
    "BaseProviderAdapter",
    "GitHubMockAdapter",
    "SlackMockAdapter",
    "ProviderAdapterFactory",
    "ProviderIntegrationError",
    "UnsupportedProviderError",
    "InvalidAdapterConfigError",
    "ProviderConnectionTimeoutError",
    "ProviderAuthenticationError",
    "get_provider_adapter",
    "register_provider_adapter",
]

