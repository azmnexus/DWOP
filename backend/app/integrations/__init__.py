"""Provider adapters for external workforce tooling (Oladotun's domain)."""
from app.integrations.base import BaseProviderAdapter
from app.integrations.factory import get_provider_adapter, register_provider_adapter
from app.integrations.github_mock import GitHubMockAdapter

__all__ = [
    "BaseProviderAdapter",
    "GitHubMockAdapter",
    "get_provider_adapter",
    "register_provider_adapter",
]
