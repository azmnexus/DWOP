"""Typed result data structure for third-party provider adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AdapterResult:
    """Immutable, strongly-typed operational result returned by all BaseProviderAdapter implementations.

    Standardizes external API responses into an internal operational contract,
    shielding core domain services from provider schema volatility.
    """

    success: bool
    status: str
    provider: str
    external_reference: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -------------------------------------------------------------------------
    # Transitional Compatibility Shim (DEPRECATED)
    # -------------------------------------------------------------------------

    def __bool__(self) -> bool:
        """Transitional boolean evaluation based on success.

        .. deprecated:: Sprint 0 (P-04)
           Directly evaluate ``result.success`` instead of relying on object truthiness.
        """
        return self.success

    def __getitem__(self, item: str) -> Any:
        """Transitional dictionary subscript access.

        .. deprecated:: Sprint 0 (P-04)
           Access typed attributes directly (e.g. ``result.status``, ``result.external_reference``).
        """
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.metadata:
            return self.metadata[item]
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        """Transitional dictionary .get() lookup.

        .. deprecated:: Sprint 0 (P-04)
           Access typed attributes directly (e.g. ``result.status``, ``result.external_reference``).
        """
        try:
            return self[item]
        except KeyError:
            return default

    def to_dict(self) -> Dict[str, Any]:
        """Convert adapter result to dictionary for audit logging and JSON serialization.

        .. note::
           Use this method strictly for database audit emission and serialization,
           never for internal business logic branching.
        """
        return {
            "success": self.success,
            "status": self.status,
            "provider": self.provider,
            "external_reference": self.external_reference,
            "error": self.error,
            "metadata": dict(self.metadata),
        }
