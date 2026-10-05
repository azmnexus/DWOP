"""FastAPI dependency pipeline: token verification, offboarding guard, RBAC.

This module implements the ADR-002 hybrid model:

1. **Signature verification + claim extraction** (:func:`decode_access_token`) -
   no database access. The ``role``, ``tenant_id`` and ``perms`` claims are only
   trustworthy once the signature has been verified.
2. **The hybrid offboarding guard** - exactly *one* lightweight database query
   per authenticated request, which simultaneously verifies ``User.is_active``
   and ``Tenant.is_active`` so offboarded professionals and suspended workspaces
   lose access instantly rather than at token expiry.
3. **In-memory policy resolution** - every RBAC decision is made by
   :class:`~app.core.policy.PolicyEngine` against the signed claims. There are
   no per-endpoint permission lookups.
"""

import uuid
from typing import Any, Callable, Mapping, Sequence

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.policy import (
    Permission,
    PolicyDeniedError,
    PolicyEngine,
    PolicySubject,
    Scope,
    policy_engine,
)
from app.core.security import decode_access_token
from app.core.tenant import set_current_tenant_id
from app.models.user import User, UserRole
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=True,
)

#: Attribute used to carry the verified claims on the resolved principal for the
#: lifetime of the request. The dependency result is cached per request, so every
#: downstream guard observes the identical, signature-verified claims.
CLAIMS_ATTRIBUTE = "_policy_claims"


def credentials_exception(
    detail: str = "Could not validate credentials or token expired.",
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _deny(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Verify the Bearer JWT and resolve the live principal.

    Exactly one database query is executed
    (:meth:`UserRepository.get_lifecycle_flags`) and it is reserved for
    revocation. Authorization itself is derived from the signed claims in
    memory.
    """
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise credentials_exception()

    subject = policy_engine.subject_from_claims(payload)
    if subject.user_id is None:
        raise credentials_exception(
            "Could not validate credentials: token subject missing."
        )

    # --- The one and only per-request DB round-trip (ADR-002 Phase 3) --------
    guard = UserRepository(db).get_lifecycle_flags(subject.user_id)
    user = guard.user
    if user is None:
        raise credentials_exception(
            "Could not validate credentials: principal no longer exists."
        )
    if not user.is_active:
        raise _deny("Inactive user account.")
    if guard.tenant_is_active is False:
        raise _deny(
            "Tenant workspace is suspended. Please contact your administrator."
        )

    # A token minted against a different tenant can never act on this identity,
    # which makes the tenant_id claim load-bearing rather than decorative.
    if subject.tenant_id is not None and subject.tenant_id != user.tenant_id:
        raise credentials_exception(
            "Could not validate credentials: tenant claim mismatch."
        )

    setattr(user, CLAIMS_ATTRIBUTE, payload)

    # Tenant context is always sourced from the authoritative user row, never
    # from the attacker-controllable X-Tenant-ID header set by the middleware.
    set_current_tenant_id(user.tenant_id)
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the authenticated user account and its tenant remain active.

    Both flags were already verified inside the single guard query in
    :func:`get_current_user`; this dependency is the explicit contract that every
    guarded endpoint depends on.
    """
    if not current_user.is_active:
        raise _deny("Inactive user account.")
    return current_user


def claims_for(current_user: User) -> Mapping[str, Any]:
    """Return the signature-verified claims attached to a resolved principal.

    Falls back to synthesizing claims from the authoritative user row so that
    service-layer callers outside the HTTP pipeline still resolve RBAC through
    the same in-memory matrix instead of hardcoded role comparisons.
    """
    claims = getattr(current_user, CLAIMS_ATTRIBUTE, None)
    if isinstance(claims, Mapping):
        return claims
    role = getattr(current_user.role, "value", current_user.role)
    return {
        "sub": str(current_user.id),
        "tenant_id": str(current_user.tenant_id),
        "role": str(role) if role else None,
        "email": current_user.email,
    }


def get_policy_subject(current_user: User) -> PolicySubject:
    """Build the in-memory authorization subject from verified claims."""
    return policy_engine.subject_from_claims(claims_for(current_user))


def get_current_policy_subject(
    current_user: User = Depends(get_current_active_user),
) -> PolicySubject:
    """Dependency exposing the verified, in-memory authorization subject."""
    return get_policy_subject(current_user)


# =============================================================================
# RBAC guards - all decisions resolved in application memory from signed claims
# =============================================================================
def require_permissions(*permissions: str) -> Callable[..., User]:
    """Build a dependency requiring *all* of the given permissions.

    Evaluated entirely in memory against the signed JWT claims. Authority may be
    satisfied by the caller's role or by a derived scope (for example
    ``team_lead``).

    The resource binding of a derived scope is deliberately *not* inferred from
    request input here. No client-supplied header, query parameter or body field
    participates in an authorization decision. When a permission is held only by
    a resource-bound scope, this guard fails closed and the endpoint must resolve
    the resource first and call :func:`enforce_scope_boundary` with the trusted
    team identifier it loaded from the database.
    """
    required: Sequence[str] = tuple(permissions)

    def _guard(
        current_user: User = Depends(get_current_active_user),
        subject: PolicySubject = Depends(get_current_policy_subject),
    ) -> User:
        try:
            for permission in required:
                policy_engine.enforce(
                    subject, permission, resource_tenant_id=current_user.tenant_id
                )
        except PolicyDeniedError as exc:
            raise _deny(exc.decision.reason)
        return current_user

    return _guard


def require_any_permission(*permissions: str) -> Callable[..., User]:
    """Build a dependency requiring at least one of the given permissions."""
    required: Sequence[str] = tuple(permissions)

    def _guard(
        current_user: User = Depends(get_current_active_user),
        subject: PolicySubject = Depends(get_current_policy_subject),
    ) -> User:
        for permission in required:
            if policy_engine.can(
                subject, permission, resource_tenant_id=current_user.tenant_id
            ):
                return current_user
        raise _deny(
            f"Access denied: role '{subject.role}' does not grant any of "
            f"{sorted(required)}."
        )

    return _guard


def require_roles(*roles: Any) -> Callable[..., User]:
    """Build a dependency restricted to the given roles."""
    allowed = tuple(roles)

    def _guard(
        current_user: User = Depends(get_current_active_user),
        subject: PolicySubject = Depends(get_current_policy_subject),
    ) -> User:
        if policy_engine.has_role(subject, *allowed):
            return current_user
        readable = sorted(str(getattr(role, "value", role)) for role in allowed)
        raise _deny(
            f"Forbidden: requires one of {readable} (your role: {subject.role})"
        )

    return _guard


def require_admin(
    current_user: User = Depends(get_current_active_user),
    subject: PolicySubject = Depends(get_current_policy_subject),
) -> User:
    """RBAC Guard: Enforce ADMIN authority (resolved by the in-memory engine)."""
    if not policy_engine.has_role(subject, UserRole.ADMIN):
        raise _deny("Admin privileges required for this operation.")
    return current_user


def require_admin_or_manager(
    current_user: User = Depends(get_current_active_user),
    subject: PolicySubject = Depends(get_current_policy_subject),
) -> User:
    """RBAC Guard: Enforce ADMIN or MANAGER authority."""
    if not policy_engine.has_role(subject, UserRole.ADMIN, UserRole.MANAGER):
        raise _deny("Admin or Manager privileges required for this operation.")
    return current_user


def enforce_tenant_boundary(
    resource_tenant_id: uuid.UUID,
    subject: PolicySubject = Depends(get_current_policy_subject),
) -> PolicySubject:
    """Dependency enforcing that a resource belongs to the caller's tenant.

    Tenant isolation is never delegated to role breadth: a cross-tenant
    identifier is rejected even for an ADMIN token.
    """
    decision = policy_engine.check_tenant_boundary(
        subject, resource_tenant_id, permission=Permission.TENANT_READ
    )
    if not decision.allowed:
        raise _deny(decision.reason)
    return subject


def enforce_scope_boundary(
    resource_team_id: uuid.UUID,
    scope: str = Scope.TEAM_LEAD,
    subject: PolicySubject = Depends(get_current_policy_subject),
) -> PolicySubject:
    """Dependency enforcing that a resource falls inside a derived scope.

    Call this with a team identifier the endpoint has already loaded from the
    database, never with a value taken straight from the request. Team Lead
    authority is resource-bound: holding the ``team_lead`` scope is necessary but
    not sufficient, the target team must also appear in the caller's signed
    ``lead_teams`` binding.
    """
    scope_name = str(scope).strip().lower()
    decision = policy_engine.check_scope_boundary(
        subject, scope_name, resource_team_id, permission=f"scope:{scope_name}"
    )
    if not decision.allowed:
        raise _deny(decision.reason)
    return subject


#: Pre-composed guards for the endpoint-level authority used across the API.
require_department_admin = require_permissions(Permission.DEPARTMENTS_MANAGE)
require_team_admin = require_permissions(Permission.TEAMS_MANAGE)
require_client_admin = require_permissions(Permission.CLIENTS_MANAGE)
require_project_admin = require_permissions(Permission.PROJECTS_MANAGE)
require_bulk_import = require_permissions(Permission.PEOPLE_BULK_IMPORT)
require_intake = require_permissions(Permission.PEOPLE_INTAKE)
require_template_author = require_permissions(Permission.ONBOARDING_TEMPLATES_MANAGE)
require_run_creator = require_permissions(Permission.ONBOARDING_RUNS_CREATE)
require_allocator = require_permissions(Permission.ASSIGNMENTS_ALLOCATE)
require_assignment_update = require_permissions(Permission.ASSIGNMENTS_UPDATE)
require_access_approver = require_permissions(Permission.ACCESS_APPROVE)
require_access_provisioner = require_permissions(Permission.ACCESS_PROVISION)
require_access_revocer = require_permissions(Permission.ACCESS_REVOKE)
require_integration_admin = require_permissions(Permission.INTEGRATIONS_MANAGE)
require_audit_reader = require_permissions(Permission.AUDIT_READ)
require_audit_exporter = require_permissions(Permission.AUDIT_EXPORT)
require_user_admin = require_permissions(Permission.USERS_MANAGE)

__all__ = [
    "CLAIMS_ATTRIBUTE",
    "Permission",
    "PolicyEngine",
    "PolicySubject",
    "Scope",
    "claims_for",
    "enforce_scope_boundary",
    "enforce_tenant_boundary",
    "get_current_active_user",
    "get_current_policy_subject",
    "get_current_user",
    "get_policy_subject",
    "oauth2_scheme",
    "policy_engine",
    "require_access_approver",
    "require_access_provisioner",
    "require_access_revocer",
    "require_admin",
    "require_admin_or_manager",
    "require_allocator",
    "require_any_permission",
    "require_assignment_update",
    "require_audit_exporter",
    "require_audit_reader",
    "require_bulk_import",
    "require_client_admin",
    "require_department_admin",
    "require_integration_admin",
    "require_intake",
    "require_permissions",
    "require_project_admin",
    "require_roles",
    "require_run_creator",
    "require_team_admin",
    "require_template_author",
    "require_user_admin",
]