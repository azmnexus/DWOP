"""In-Memory RBAC Policy Engine (ADR-002: Stateless RBAC Scaling).

The policy engine resolves every authorization question *without touching the
database, cache, or network*. It is a pure function of the cryptographically
signed claims carried inside the access JWT, evaluated against a frozen policy
matrix that lives in application memory.

Design invariants (enforced by construction, not convention):

1. **No I/O.** :class:`PolicyEngine` accepts no database session, no HTTP
   client, and no cache handle. Evaluation is a dict lookup plus set membership
   tests: sub-millisecond, zero infrastructure dependencies.
2. **Signed claims only.** The role, tenant and permission claims are read from
   the JWT payload *after* signature verification by :mod:`app.core.security`.
   The engine never trusts client-supplied headers, query parameters or body
   fields for authorization decisions.
3. **Fail closed.** A missing, blank or unrecognised role is a denial. A missing
   tenant claim is a denial. Any unknown permission constant is a denial.
4. **Tenant boundary is mandatory.** Resource-scoped evaluations compare the
   subject's tenant claim against the resource tenant and deny on mismatch, even
   when the role alone would have permitted the action.

The one and only database round-trip on an authenticated request is the
offboarding guard in :mod:`app.core.dependencies`, which exists purely to
support *instant revocation* of deactivated users and suspended tenants. All RBAC
computation stays here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, FrozenSet, Iterable, Mapping, Optional, Sequence

from app.models.user import UserRole

__all__ = [
    "Permission",
    "PolicyDecision",
    "PolicyEngine",
    "PolicyError",
    "PolicyDeniedError",
    "PolicySubject",
    "MEMBER_PERMISSIONS",
    "MANAGER_PERMISSIONS",
    "ADMIN_PERMISSIONS",
    "POLICY_MATRIX",
    "policy_engine",
]


# =============================================================================
# Permission Catalogue
# =============================================================================
# Canonical identifier grammar: ``<domain>:<resource>[:<action>]``.
# The ``:self`` / ``:all`` suffix pair encodes resource-ownership scoping so the
# matrix can express "read only my own" versus "read every record in tenant".
class Permission:
    """Canonical permission identifiers evaluated by :class:`PolicyEngine`."""

    # --- Tenant / workspace -------------------------------------------------
    TENANT_READ = "tenant:read"
    TENANT_UPDATE = "tenant:update"

    # --- Organization structure --------------------------------------------
    DEPARTMENT_READ = "department:read"
    DEPARTMENT_MANAGE = "department:manage"
    TEAM_READ = "team:read"
    TEAM_MANAGE = "team:manage"
    CLIENT_READ = "client:read"
    CLIENT_MANAGE = "client:manage"
    PROJECT_READ = "project:read"
    PROJECT_MANAGE = "project:manage"

    # --- Workforce / professionals -----------------------------------------
    PROFESSIONAL_READ_SELF = "professional:read:self"
    PROFESSIONAL_READ_ALL = "professional:read:all"
    PROFESSIONAL_INTAKE = "professional:intake"
    PROFESSIONAL_BULK_IMPORT = "professional:bulk_import"
    PROFESSIONAL_UPDATE = "professional:update"

    # --- Onboarding --------------------------------------------------------
    ONBOARDING_TEMPLATE_READ = "onboarding:template:read"
    ONBOARDING_TEMPLATE_MANAGE = "onboarding:template:manage"
    ONBOARDING_RUN_READ_SELF = "onboarding:run:read:self"
    ONBOARDING_RUN_READ_ALL = "onboarding:run:read:all"
    ONBOARDING_RUN_CREATE = "onboarding:run:create"
    ONBOARDING_ITEM_COMPLETE_SELF = "onboarding:item:complete:self"
    ONBOARDING_ITEM_UPDATE_ANY = "onboarding:item:update:any"

    # --- Assignments / capacity -------------------------------------------
    ASSIGNMENT_READ_SELF = "assignment:read:self"
    ASSIGNMENT_READ_ALL = "assignment:read:all"
    ASSIGNMENT_ALLOCATE = "assignment:allocate"
    ASSIGNMENT_UPDATE = "assignment:update"

    # --- Access request lifecycle -----------------------------------------
    ACCESS_REQUEST_READ_SELF = "access:request:read:self"
    ACCESS_REQUEST_READ_ALL = "access:request:read:all"
    ACCESS_REQUEST_CREATE_SELF = "access:request:create:self"
    ACCESS_REQUEST_CREATE_ANY = "access:request:create:any"
    ACCESS_REQUEST_APPROVE = "access:request:approve"
    ACCESS_REQUEST_PROVISION = "access:request:provision"
    ACCESS_REQUEST_REVOKE = "access:request:revoke"
    ACCESS_INTEGRATION_MANAGE = "access:integration:manage"

    # --- Audit & governance -------------------------------------------------
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"

    # --- Identity administration -------------------------------------------
    USER_MANAGE = "user:manage"

    # --- Superuser sentinel -------------------------------------------------
    # Never granted to a built-in role. Recognised on evaluation so that a
    # future custom role can be issued a wildcard without changing the engine.
    WILDCARD = "*"


# =============================================================================
# The Policy Matrix (frozen, in application memory)
# =============================================================================
# MEMBER: self-service only. Scoped by ownership, never by tenant-wide fan-out.
MEMBER_PERMISSIONS: FrozenSet[str] = frozenset(
    {
        Permission.TENANT_READ,
        Permission.DEPARTMENT_READ,
        Permission.TEAM_READ,
        Permission.CLIENT_READ,
        Permission.PROJECT_READ,
        Permission.PROFESSIONAL_READ_SELF,
        Permission.ONBOARDING_TEMPLATE_READ,
        Permission.ONBOARDING_RUN_READ_SELF,
        Permission.ONBOARDING_ITEM_COMPLETE_SELF,
        Permission.ASSIGNMENT_READ_SELF,
        Permission.ACCESS_REQUEST_READ_SELF,
        Permission.ACCESS_REQUEST_CREATE_SELF,
    }
)

# MANAGER: departmental oversight. Inherits every MEMBER capability and gains
# tenant-wide read plus intake, onboarding run instantiation, capacity
# allocation, and access approval restricted to direct reports (the direct-report
# rule itself stays a resource-scoped check in AccessService).
MANAGER_PERMISSIONS: FrozenSet[str] = frozenset(
    MEMBER_PERMISSIONS
    | {
        Permission.PROFESSIONAL_READ_ALL,
        Permission.PROFESSIONAL_INTAKE,
        Permission.ONBOARDING_RUN_READ_ALL,
        Permission.ONBOARDING_RUN_CREATE,
        Permission.ASSIGNMENT_READ_ALL,
        Permission.ASSIGNMENT_ALLOCATE,
        Permission.ASSIGNMENT_UPDATE,
        Permission.ACCESS_REQUEST_READ_ALL,
        Permission.ACCESS_REQUEST_CREATE_ANY,
        Permission.ACCESS_REQUEST_APPROVE,
        Permission.ACCESS_REQUEST_PROVISION,
    }
)

# ADMIN: global governance. Explicitly enumerated (never the ``*`` wildcard) so
# the JWT always carries a concrete, auditable permission list.
ADMIN_PERMISSIONS: FrozenSet[str] = frozenset(
    MANAGER_PERMISSIONS
    | {
        Permission.TENANT_UPDATE,
        Permission.DEPARTMENT_MANAGE,
        Permission.TEAM_MANAGE,
        Permission.CLIENT_MANAGE,
        Permission.PROJECT_MANAGE,
        Permission.PROFESSIONAL_BULK_IMPORT,
        Permission.PROFESSIONAL_UPDATE,
        Permission.ONBOARDING_TEMPLATE_MANAGE,
        Permission.ONBOARDING_ITEM_UPDATE_ANY,
        Permission.ACCESS_REQUEST_REVOKE,
        Permission.ACCESS_INTEGRATION_MANAGE,
        Permission.AUDIT_READ,
        Permission.AUDIT_EXPORT,
        Permission.USER_MANAGE,
    }
)

#: Role value -> effective permission set. Immutable snapshot of the policy.
POLICY_MATRIX: Mapping[str, FrozenSet[str]] = {
    UserRole.MEMBER.value: MEMBER_PERMISSIONS,
    UserRole.MANAGER.value: MANAGER_PERMISSIONS,
    UserRole.ADMIN.value: ADMIN_PERMISSIONS,
}


# =============================================================================
# Exceptions
# =============================================================================
class PolicyError(Exception):
    """Base class for policy engine failures."""


class PolicyDeniedError(PolicyError):
    """Raised when the in-memory engine denies a policy evaluation."""

    def __init__(self, decision: "PolicyDecision") -> None:
        self.decision = decision
        super().__init__(decision.reason)


# =============================================================================
# Value objects
# =============================================================================
@dataclass(frozen=True)
class PolicySubject:
    """Normalized, immutable authorization subject.

    Built exclusively from verified JWT claims (or from a ``User`` row when a
    service layer needs to evaluate a resource rule outside the HTTP pipeline).
    """

    user_id: Optional[uuid.UUID] = None
    tenant_id: Optional[uuid.UUID] = None
    role: Optional[str] = None
    email: Optional[str] = None
    claims: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_known_role(self) -> bool:
        return self.role in POLICY_MATRIX


@dataclass(frozen=True)
class PolicyDecision:
    """Outcome of a single in-memory policy evaluation."""

    allowed: bool
    permission: str
    role: Optional[str]
    reason: str
    resource_tenant_id: Optional[uuid.UUID] = None

    def __bool__(self) -> bool:
        return self.allowed

    @property
    def denied(self) -> bool:
        return not self.allowed


def _coerce_uuid(value: Any) -> Optional[uuid.UUID]:
    """Best-effort conversion of a claim/attribute value to ``uuid.UUID``."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _coerce_role(value: Any) -> Optional[str]:
    """Normalize a role claim/attribute to its canonical uppercase value."""
    if value is None:
        return None
    raw = getattr(value, "value", value)
    role = str(raw).strip()
    return role.upper() or None


# =============================================================================
# Policy Engine
# =============================================================================
class PolicyEngine:
    """Stateless, in-memory RBAC evaluator.

    The engine holds an immutable snapshot of the policy matrix. It performs no
    I/O of any kind: no SQL, no cache lookup, no network call. Resolution cost
    is a dictionary lookup plus frozenset membership tests.
    """

    def __init__(self, matrix: Optional[Mapping[str, Iterable[str]]] = None) -> None:
        source = POLICY_MATRIX if matrix is None else matrix
        # Defensive copy so post-construction mutation cannot alter decisions.
        self._matrix: Mapping[str, FrozenSet[str]] = {
            _coerce_role(role) or "": frozenset(perms)
            for role, perms in source.items()
        }
        self._all_permissions: FrozenSet[str] = frozenset(
            perm for perms in self._matrix.values() for perm in perms
        )

    # -- introspection -------------------------------------------------------
    @property
    def matrix(self) -> Mapping[str, FrozenSet[str]]:
        """The frozen role -> permissions snapshot this engine evaluates."""
        return self._matrix

    @property
    def all_permissions(self) -> FrozenSet[str]:
        """Every permission identifier known to the policy."""
        return self._all_permissions

    # -- subject normalization ----------------------------------------------
    def subject_from_claims(self, claims: Mapping[str, Any]) -> PolicySubject:
        """Build a :class:`PolicySubject` from verified JWT claims."""
        return PolicySubject(
            user_id=_coerce_uuid(claims.get("sub")),
            tenant_id=_coerce_uuid(claims.get("tenant_id")),
            role=_coerce_role(claims.get("role")),
            email=claims.get("email"),
            claims=dict(claims),
        )

    def subject_from_principal(self, principal: Any) -> PolicySubject:
        """Build a :class:`PolicySubject` from a ``User`` ORM row, claims, or role.

        Services that evaluate resource-scoped rules outside the HTTP pipeline
        pass the authenticated ``User`` directly; the role and tenant are still
        read from the in-memory identity, never from an extra permission query.
        A bare role (``UserRole`` or its string value) is also accepted so that
        non-HTTP callers such as state-machine transition guards can resolve
        authority without constructing a principal.
        """
        if isinstance(principal, PolicySubject):
            return principal
        if isinstance(principal, Mapping):
            return self.subject_from_claims(principal)
        if _coerce_role(principal) in self._matrix:
            return PolicySubject(role=_coerce_role(principal))
        return PolicySubject(
            user_id=_coerce_uuid(getattr(principal, "id", None)),
            tenant_id=_coerce_uuid(getattr(principal, "tenant_id", None)),
            role=_coerce_role(getattr(principal, "role", None)),
            email=getattr(principal, "email", None),
            claims={},
        )

    # -- permission resolution ----------------------------------------------
    def permissions_for_role(self, role: Any) -> FrozenSet[str]:
        """Resolve the effective permission set for a role. Pure memory lookup."""
        normalized = _coerce_role(role)
        if normalized is None:
            return frozenset()
        return self._matrix.get(normalized, frozenset())

    def permissions_for(self, principal: Any) -> FrozenSet[str]:
        """Resolve the effective permission set for an already-normalized subject.

        The ``role`` claim is authoritative: the matrix is the single source of
        truth for what a role may do. The embedded ``perms`` claim is a signed
        convenience artefact (surfaced to clients and the audit ledger) and is
        never used to widen authority, so a matrix change takes effect on the
        next request without re-issuing tokens.
        """
        return self.permissions_for_role(self.subject_from_principal(principal).role)

    def has_permission(self, principal: Any, permission: str) -> bool:
        """Fast boolean membership test used by dependency guards."""
        permissions = self.permissions_for(principal)
        if Permission.WILDCARD in permissions:
            return True
        return permission in permissions

    def has_any_permission(self, principal: Any, permissions: Sequence[str]) -> bool:
        return any(self.has_permission(principal, perm) for perm in permissions)

    def has_all_permissions(self, principal: Any, permissions: Sequence[str]) -> bool:
        return all(self.has_permission(principal, perm) for perm in permissions)

    def has_role(self, principal: Any, *roles: Any) -> bool:
        """Role membership test resolved from the in-memory matrix."""
        subject = self.subject_from_principal(principal)
        return subject.role in {_coerce_role(role) for role in roles if role is not None}

    # -- tenant boundary ----------------------------------------------------
    def check_tenant_boundary(
        self,
        principal: Any,
        resource_tenant_id: Any,
        *,
        permission: str = "",
    ) -> PolicyDecision:
        """Evaluate the mandatory tenant boundary check.

        Retained in full even though permissions are resolved in memory: a
        cross-tenant read is a data-isolation breach, not an RBAC miss.
        """
        subject = self.subject_from_principal(principal)
        target = _coerce_uuid(resource_tenant_id)
        label = permission or "tenant_boundary"

        if subject.tenant_id is None:
            return PolicyDecision(
                allowed=False,
                permission=label,
                role=subject.role,
                reason="Access denied: token carries no tenant claim.",
                resource_tenant_id=target,
            )
        if target is None:
            return PolicyDecision(
                allowed=False,
                permission=label,
                role=subject.role,
                reason="Access denied: resource tenant could not be determined.",
                resource_tenant_id=target,
            )
        if subject.tenant_id != target:
            return PolicyDecision(
                allowed=False,
                permission=label,
                role=subject.role,
                reason="Access denied: cross-tenant boundary violation.",
                resource_tenant_id=target,
            )
        return PolicyDecision(
            allowed=True,
            permission=label,
            role=subject.role,
            reason="Tenant boundary satisfied.",
            resource_tenant_id=target,
        )

    # -- full evaluation ----------------------------------------------------
    def authorize(
        self,
        principal: Any,
        permission: str,
        *,
        resource_tenant_id: Any = None,
        enforce_tenant_boundary: bool = True,
    ) -> PolicyDecision:
        """Evaluate a permission request entirely in application memory.

        Order of evaluation is deliberate and fail-closed: role validity first,
        then tenant boundary, then permission membership. Tenant checks can
        never be skipped by holding a broader role.
        """
        subject = self.subject_from_principal(principal)

        if subject.role is None:
            return PolicyDecision(
                allowed=False,
                permission=permission,
                role=None,
                reason="Access denied: token carries no role claim.",
                resource_tenant_id=_coerce_uuid(resource_tenant_id),
            )
        if subject.role not in self._matrix:
            return PolicyDecision(
                allowed=False,
                permission=permission,
                role=subject.role,
                reason=(
                    f"Access denied: role '{subject.role}' is not present in the "
                    "policy matrix."
                ),
                resource_tenant_id=_coerce_uuid(resource_tenant_id),
            )

        if enforce_tenant_boundary:
            boundary = self.check_tenant_boundary(
                subject, resource_tenant_id, permission=permission
            )
            if not boundary.allowed:
                return boundary

        permissions = self.permissions_for_role(subject.role)
        if Permission.WILDCARD in permissions or permission in permissions:
            return PolicyDecision(
                allowed=True,
                permission=permission,
                role=subject.role,
                reason=f"Role '{subject.role}' grants '{permission}'.",
                resource_tenant_id=_coerce_uuid(resource_tenant_id),
            )

        return PolicyDecision(
            allowed=False,
            permission=permission,
            role=subject.role,
            reason=(
                f"Access denied: role '{subject.role}' does not grant "
                f"'{permission}'."
            ),
            resource_tenant_id=_coerce_uuid(resource_tenant_id),
        )

    def can(
        self,
        principal: Any,
        permission: str,
        *,
        resource_tenant_id: Any = None,
        enforce_tenant_boundary: bool = True,
    ) -> bool:
        """Boolean convenience wrapper around :meth:`authorize`."""
        return bool(
            self.authorize(
                principal,
                permission,
                resource_tenant_id=resource_tenant_id,
                enforce_tenant_boundary=enforce_tenant_boundary,
            )
        )

    def enforce(
        self,
        principal: Any,
        permission: str,
        *,
        resource_tenant_id: Any = None,
        enforce_tenant_boundary: bool = True,
    ) -> PolicyDecision:
        """Authorize or raise :class:`PolicyDeniedError` (fail closed)."""
        decision = self.authorize(
            principal,
            permission,
            resource_tenant_id=resource_tenant_id,
            enforce_tenant_boundary=enforce_tenant_boundary,
        )
        if not decision.allowed:
            raise PolicyDeniedError(decision)
        return decision

    # -- token issuance support --------------------------------------------
    def permissions_for_token(self, role: Any) -> Sequence[str]:
        """Sorted permission list to embed as the signed ``perms`` claim."""
        return sorted(self.permissions_for_role(role))


#: Process-wide engine singleton. Immutable and safe to share across threads.
policy_engine = PolicyEngine()