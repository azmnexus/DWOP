"""Typed result data structure for third-party provider adapters."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True, init=False)
class AdapterResult:
    """Immutable, strongly-typed operational result returned by all BaseProviderAdapter implementations.

    Standardizes external API responses into an internal operational contract,
    shielding core domain services from provider schema volatility.

    Per Implementation Directive:
    - Primary external identifier field: `external_id`
    - Primary error description field: `error_message`
    - Aliases `external_reference` and `error` are maintained for full backward compatibility.
    """

    success: bool
    status: str
    provider: str
    external_id: Optional[str]
    error_message: Optional[str]
    metadata: Dict[str, Any]

    def __init__(
        self,
        success: bool,
        status: str,
        provider: str,
        external_id: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        external_reference: Optional[str] = None,
        error: Optional[str] = None,
    ):
        object.__setattr__(self, "success", success)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "provider", provider)
        resolved_ext_id = external_id if external_id is not None else external_reference
        object.__setattr__(self, "external_id", resolved_ext_id)
        resolved_error = error_message if error_message is not None else error
        object.__setattr__(self, "error_message", resolved_error)
        object.__setattr__(self, "metadata", metadata or {})

    # -------------------------------------------------------------------------
    # Backward Compatibility Properties (Aliased per Directive)
    # -------------------------------------------------------------------------

    @property
    def external_reference(self) -> Optional[str]:
        """Backward-compatible alias for ``external_id`` per Directive specification."""
        return self.external_id

    @property
    def error(self) -> Optional[str]:
        """Backward-compatible alias for ``error_message`` per Directive specification."""
        return self.error_message

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
           Access typed attributes directly (e.g. ``result.status``, ``result.external_id``).
        """
        if item in ("external_reference", "external_id"):
            return self.external_id
        if item in ("error", "error_message"):
            return self.error_message
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.metadata:
            return self.metadata[item]
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        """Transitional dictionary .get() lookup.

        .. deprecated:: Sprint 0 (P-04)
           Access typed attributes directly (e.g. ``result.status``, ``result.external_id``).
        """
        try:
            val = self[item]
            return val if val is not None else default
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
            "external_id": self.external_id,
            "external_reference": self.external_id,
            "error_message": self.error_message,
            "error": self.error_message,
            "metadata": dict(self.metadata),
        }
