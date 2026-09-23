"""Provider integration exception hierarchy."""
from __future__ import annotations


class ProviderIntegrationError(Exception):
    """Base error for provider adapter construction and communication failures."""


class UnsupportedProviderError(ProviderIntegrationError, ValueError):
    """Raised when no adapter implementation is registered for a provider."""


class InvalidAdapterConfigError(ProviderIntegrationError, ValueError):
    """Raised when provider adapter configuration is malformed or incomplete."""


class ProviderConnectionTimeoutError(ProviderIntegrationError):
    """Raised when communication with an external provider times out.

    Raised by mock adapters when ``simulate_timeout=True`` is configured.
    TODO: In live provider implementations (e.g. GitHub REST API / Slack WebClient),
    translate HTTP 408/504 and network timeout errors to ProviderConnectionTimeoutError.
    """


class ProviderAuthenticationError(ProviderIntegrationError):
    """Raised when external provider credentials or tokens are rejected.

    Raised by mock adapters when ``simulate_auth_error=True`` or invalid token is configured.
    TODO: In live provider implementations, translate HTTP 401/403 and OAuth token
    rejection responses to ProviderAuthenticationError.
    """
