"""Provider adapter registry and construction helpers."""
from __future__ import annotations

from typing import Any, Dict, Type

from app.integrations.base import BaseProviderAdapter
from app.integrations.github_mock import GitHubMockAdapter


_PROVIDER_ADAPTERS: Dict[str, Type[BaseProviderAdapter]] = {
    # Sprint 0 deliberately resolves GitHub to the safe mock implementation.
    "github": GitHubMockAdapter,
}


def register_provider_adapter(name: str, adapter_cls: Type[BaseProviderAdapter]) -> None:
    """Register an adapter implementation behind the common provider contract."""
    normalized = name.strip().lower()
    if not normalized:
        raise ValueError("Provider name cannot be empty.")
    if not isinstance(adapter_cls, type) or not issubclass(adapter_cls, BaseProviderAdapter):
        raise TypeError("Provider adapters must inherit from BaseProviderAdapter.")
    _PROVIDER_ADAPTERS[normalized] = adapter_cls


def get_provider_adapter(
    provider: str,
    tenant_id: str,
    credentials: Dict[str, Any] | None = None,
) -> BaseProviderAdapter:
    """Construct a provider through ``BaseProviderAdapter`` rather than core code."""
    normalized = provider.strip().lower()
    if not normalized:
        raise ValueError("Provider name cannot be empty.")
    if not tenant_id.strip():
        raise ValueError("tenant_id cannot be empty.")

    adapter_cls = _PROVIDER_ADAPTERS.get(normalized)
    if adapter_cls is None:
        raise ValueError(f"Unsupported provider adapter: {provider}")
    return adapter_cls(tenant_id=tenant_id, credentials=credentials or {})
