"""
RBAC & Tenant-aware dependencies.

- get_current_user: validates JWT, loads DB user, sets tenant ContextVar
- require_roles: dependency factory enforcing ADMIN/MANAGER/MEMBER boundaries
- get_current_tenant_id: returns scoped tenant UUID
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import decode_access_token
from backend.core.tenancy import get_tenant_id, set_current_user_claims, set_tenant_id
from backend.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        tenant_id: str | None = payload.get("tenant_id") or payload.get("tid")
        role: str | None = payload.get("role")
        if user_id is None or tenant_id is None:
            raise credentials_exception
        # Set tenant context for downstream query scoping
        set_tenant_id(tenant_id)
        set_current_user_claims(payload)
    except JWTError:
        raise credentials_exception

    # Load user and enforce tenant + active
    try:
        uid = uuid.UUID(user_id)
        tid = uuid.UUID(tenant_id)  # type: ignore[arg-type]
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uid, User.tenant_id == tid))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    # Attach claims for RBAC without extra DB hit if needed
    user._claims = payload  # type: ignore[attr-defined]
    return user


async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


def require_roles(*allowed: UserRole | str):
    """
    RBAC guard factory.
    Usage:
        @router.post(..., dependencies=[Depends(require_roles(UserRole.ADMIN))])
        or as a dependency that returns the user:
        current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
    """
    allowed_values = {r.value if isinstance(r, UserRole) else r for r in allowed}

    async def _guard(current_user: Annotated[User, Depends(get_current_user)]):
        user_role = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)
        # Claims role is secondary; DB role is source of truth
        if user_role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: requires one of {sorted(allowed_values)} (your role: {user_role})",
            )
        return current_user

    return _guard


# Shorthand dependencies
RequireAdmin = require_roles(UserRole.ADMIN)
RequireManager = require_roles(UserRole.ADMIN, UserRole.MANAGER)
RequireAnyAuthenticated = get_current_user  # any active user


async def get_current_tenant_id(current_user: Annotated[User, Depends(get_current_user)]) -> uuid.UUID:
    """Convenience: return tenant_id from ContextVar (already set by get_current_user)."""
    return get_tenant_id()
