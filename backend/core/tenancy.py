"""
Strict Multi-Tenancy via async-safe ContextVar.

Every request's tenant_id is extracted from the JWT (claims: tenant_id / tid)
and stored in a ContextVar. All ORM queries MUST scope to this value to prevent
cross-tenant leakage. This module is the single source of truth for tenant context.

Usage:
    set_tenant_id(uuid)   # middleware / dependency
    get_tenant_id()       # service / repository layer
    tenant_aware_query(stmt, model)  # optional helper

The ContextVar is automatically isolated per asyncio Task / request.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Optional

from fastapi import HTTPException, status

# Core ContextVar - async-safe, request-scoped
_tenant_ctx: ContextVar[Optional[uuid.UUID]] = ContextVar("_tenant_ctx", default=None)
_current_user_ctx: ContextVar[Optional[dict]] = ContextVar("_current_user_ctx", default=None)


def set_tenant_id(tenant_id: uuid.UUID | str | None) -> None:
    """Set active tenant_id for current async context."""
    if isinstance(tenant_id, str):
        tenant_id = uuid.UUID(tenant_id)
    _tenant_ctx.set(tenant_id)


def get_tenant_id(*, required: bool = True) -> uuid.UUID:
    """
    Retrieve active tenant_id.
    Raises 400 if required and not set (prevents accidental unscoped queries).
    """
    tid = _tenant_ctx.get()
    if tid is None and required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context not set. Missing or invalid JWT tenant claim.",
        )
    return tid  # type: ignore[return-value]


def clear_tenant_id() -> None:
    _tenant_ctx.set(None)


def get_tenant_id_optional() -> Optional[uuid.UUID]:
    return _tenant_ctx.get()


# ---- Current user context helpers (optional, for auditing) ----
def set_current_user_claims(claims: dict) -> None:
    _current_user_ctx.set(claims)


def get_current_user_claims() -> Optional[dict]:
    return _current_user_ctx.get()


# ---- Query scoping helper ----
def tenant_filter(model, tenant_id: uuid.UUID | None = None):
    """
    Returns a SQLAlchemy filter clause that scopes to tenant_id.
    Ensures every table except TENANT is filtered.
    Usage: stmt = select(User).where(tenant_filter(User))
    """
    tid = tenant_id or get_tenant_id()
    if not hasattr(model, "tenant_id"):
        raise ValueError(f"Model {model.__name__} has no tenant_id - use only for tenant-scoped tables")
    return model.tenant_id == tid  # type: ignore[attr-defined]
