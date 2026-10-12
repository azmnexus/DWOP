"""Stateless RBAC Policy Engine for horizontal scaling (ADR-002, Tasks O-01 & O-02).

Evaluates cryptographically signed JWT claims against immutable, frozen
configuration tables that live in application memory.

Two authorities compose here:

**Roles** — the three locked enterprise tiers (``ADMIN``, ``MANAGER``,
``MEMBER``). These are the only roles persisted in ``users.role``. Role authority
is tenant-wide.

**Derived scopes** — situational authority computed from existing relational
data, most importantly ``team_lead``, derived from ``Team.team_lead_id``. Scope
authority is *never* a fourth global role: no row in the database grants it, no
enum member represents it, and it cannot be self-assigned. Scope authority is
always narrower than the role authority that carries it, and is always bound to
the specific resources named in the signed ``lead_teams`` claim.

Design invariants (enforced by construction, not convention):

1. **No I/O.** :class:`PolicyEngine` accepts no database session, no HTTP client
   and no cache handle. Evaluation is a dict lookup plus frozenset membership
   tests: sub-millisecond, zero infrastructure dependencies.
2. **Signed claims only.** The role, scope, tenant and permission claims are read
   from the JWT payload *after* signature verification by
   :mod:`app.core.security`. No client header, query parameter or body field ever
   influences an authorization decision.
3. **Fail closed.** A missing, blank or unrecognised role is a denial. A missing
   tenant claim is a denial. A scope-granted permission used outside its bound
   resource is a denial.
4. **Tenant boundary is mandatory.** Resource-scoped evaluations compare the
   subject's tenant claim against the resource tenant and deny on mismatch, even
   when the role alone would have permitted the action.
5. **Scope is narrower than role.** A permission granted through a derived scope
   is refused unless the resource lies inside the signed scope boundary.

The authoritative, audit-ready publication of this matrix is
``docs/rbac-matrix.md``.

The one and only database round-trip on an authenticated request remains the
offboarding guard in :mod:`app.core.dependencies`.
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
    "Scope",
    "MEMBER_PERMISSIONS",
    "MANAGER_PERMISSIONS",
    "ADMIN_PERMISSIONS",
    "TEAM_LEAD_SCOPE_PERMISSIONS",
    "POLICY_MATRIX",
    "SCOPE_MATRIX",
    "LEGACY_PERMISSION_ALIASES",
    "policy_engine",
]


# =============================================================================
# Permission Catalogue — operational formats
# =============================================================================
# Canonical grammar: ``<domain>:<action>`` or ``<domain>:<action>:<qualifier>``.
# Domains are the plural operational nouns the platform acts on. The ``:all``
# qualifier grants tenant-wide reach; its absence scopes the action to the
# caller's own records.
class Permission:
    """Operational permission identifiers evaluated by :class:`PolicyEngine`."""

    # --- Workspace -----------------------------------------------------------
    TENANT_READ = "tenant:read"
    TENANT_UPDATE = "tenant:update"

    # --- Organisation structure ---------------------------------------------
    DEPARTMENTS_READ = "departments:read"
    DEPARTMENTS_MANAGE = "departments:manage"
    TEAMS_READ = "teams:read"
    TEAMS_MANAGE = "teams:manage"
    CLIENTS_READ = "clients:read"
    CLIENTS_MANAGE = "clients:manage"
    PROJECTS_READ = "projects:read"
    PROJECTS_MANAGE = "projects:manage"

    # --- Workforce -----------------------------------------------------------
    PEOPLE_READ = "people:read"
    PEOPLE_READ_ALL = "people:read:all"
    PEOPLE_INTAKE = "people:intake"
    PEOPLE_BULK_IMPORT = "people:bulk_import"
    PEOPLE_UPDATE = "people:update"

    # --- Onboarding ----------------------------------------------------------
    ONBOARDING_TEMPLATES_READ = "onboarding:templates:read"
    ONBOARDING_TEMPLATES_MANAGE = "onboarding:templates:manage"
    ONBOARDING_RUNS_READ = "onboarding:runs:read"
    ONBOARDING_RUNS_READ_ALL = "onboarding:runs:read:all"
    ONBOARDING_RUNS_CREATE = "onboarding:runs:create"
    ONBOARDING_ITEMS_COMPLETE = "onboarding:items:complete"
    ONBOARDING_ITEMS_MANAGE = "onboarding:items:manage"

    # --- Assignments & capacity ---------------------------------------------
    ASSIGNMENTS_READ = "assignments:read"
    ASSIGNMENTS_READ_ALL = "assignments:read:all"
    ASSIGNMENTS_ALLOCATE = "assignments:allocate"
    ASSIGNMENTS_UPDATE = "assignments:update"

    # --- Access request lifecycle -------------------------------------------
    ACCESS_READ = "access:read"
    ACCESS_READ_ALL = "access:read:all"
    ACCESS_REQUEST = "access:request"
    ACCESS_REQUEST_ANY = "access:request:any"
    ACCESS_APPROVE = "access:approve"
    ACCESS_PROVISION = "access:provision"
    ACCESS_REVOKE = "access:revoke"
    INTEGRATIONS_MANAGE = "integrations:manage"

    # --- Audit & governance --------------------------------------------------
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"

    # --- Identity administration --------------------------------------------
    USERS_MANAGE = "users:manage"

    # --- Superuser sentinel --------------------------------------------------
    # Never granted to a built-in role or scope. Recognised on evaluation so a
    # future custom role can be issued a wildcard without changing the engine.
    WILDCARD = "*"


# =============================================================================
# Derived scopes — situational authority, not database roles
# =============================================================================
class Scope:
    """Names of in-memory derived scopes.

    A scope is *not* a member of :class:`~app.models.user.UserRole`. It is
    derived at token-issuance time from relational data and bound to the
    resources named in the signed claim.
    """

    #: Derived from ``Team.team_lead_id``. Grants team-bounded delegation
    #: authority. Never tenant-wide.
    TEAM_LEAD = "team_lead"


# =============================================================================
# Role Authority — the three locked enterprise tiers
# =============================================================================
# MEMBER: self-service. Every action is scoped to the caller's own records.
MEMBER_PERMISSIONS: FrozenSet[str] = frozenset(
    {
        Permission.TENANT_READ,
        Permission.DEPARTMENTS_READ,
        Permission.TEAMS_READ,
        Permission.CLIENTS_READ,
        Permission.PROJECTS_READ,
        Permission.PEOPLE_READ,
        Permission.ONBOARDING_TEMPLATES_READ,
        Permission.ONBOARDING_RUNS_READ,
        Permission.ONBOARDING_ITEMS_COMPLETE,
        Permission.ASSIGNMENTS_READ,
        Permission.ACCESS_READ,
        Permission.ACCESS_REQUEST,
    }
)

# MANAGER: departmental oversight. Inherits every MEMBER capability and gains
# tenant-wide reach over people, onboarding runs, capacity and access requests.
MANAGER_PERMISSIONS: FrozenSet[str] = frozenset(
    MEMBER_PERMISSIONS
    | {
        Permission.PEOPLE_READ_ALL,
        Permission.PEOPLE_INTAKE,
        Permission.ONBOARDING_RUNS_READ_ALL,
        Permission.ONBOARDING_RUNS_CREATE,
        Permission.ASSIGNMENTS_READ_ALL,
        Permission.ASSIGNMENTS_ALLOCATE,
        Permission.ASSIGNMENTS_UPDATE,
        Permission.ACCESS_READ_ALL,
        Permission.ACCESS_REQUEST_ANY,
        Permission.ACCESS_APPROVE,
        Permission.ACCESS_PROVISION,
    }
)

# ADMIN: global governance. Explicitly enumerated (never the ``*`` wildcard) so
# the JWT always carries a concrete, auditable permission list.
ADMIN_PERMISSIONS: FrozenSet[str] = frozenset(
    MANAGER_PERMISSIONS
    | {
        Permission.TENANT_UPDATE,
        Permission.DEPARTMENTS_MANAGE,
        Permission.TEAMS_MANAGE,
        Permission.CLIENTS_MANAGE,
        Permission.PROJECTS_MANAGE,
        Permission.PEOPLE_BULK_IMPORT,
        Permission.PEOPLE_UPDATE,
        Permission.ONBOARDING_TEMPLATES_MANAGE,
        Permission.ONBOARDING_ITEMS_MANAGE,
        Permission.ACCESS_REVOKE,
        Permission.INTEGRATIONS_MANAGE,
        Permission.AUDIT_READ,
        Permission.AUDIT_EXPORT,
        Permission.USERS_MANAGE,
    }
)

#: Role value -> effective tenant-wide permission set. Immutable snapshot.
POLICY_MATRIX: Mapping[str, FrozenSet[str]] = {
    UserRole.MEMBER.value: MEMBER_PERMISSIONS,
    UserRole.MANAGER.value: MANAGER_PERMISSIONS,
    UserRole.ADMIN.value: ADMIN_PERMISSIONS,
}


# =============================================================================
# Scope Authority — derived, resource-bound, never tenant-wide
# =============================================================================
# Team Lead authority. Note that it deliberately mirrors a *subset* of MANAGER
# authority and, unlike MANAGER, every permission granted here is bound to the
# teams named in the signed ``lead_teams`` claim. A team lead who does not lead
# team X cannot act on team X even with a valid, unexpired token.
TEAM_LEAD_SCOPE_PERMISSIONS: FrozenSet[str] = frozenset(
    {
        Permission.PEOPLE_READ_ALL,
        Permission.PEOPLE_INTAKE,
        Permission.ONBOARDING_RUNS_CREATE,
        Permission.ASSIGNMENTS_READ_ALL,
        Permission.ASSIGNMENTS_ALLOCATE,
    }
)

#: Derived scope name -> permission set it unlocks within its bound resources.
SCOPE_MATRIX: Mapping[str, FrozenSet[str]] = {
    Scope.TEAM_LEAD: TEAM_LEAD_SCOPE_PERMISSIONS,
}

#: Scopes whose grants are bound to the resources listed in the signed
#: ``lead_teams`` claim rather than applying tenant-wide.
RESOURCE_BOUND_SCOPES: FrozenSet[str] = frozenset({Scope.TEAM_LEAD})


# =============================================================================
# Legacy identifier mapping
# =============================================================================
# Pre-O-02 identifiers. Retained for read-side tolerance only, so a rolling
# deployment where old and new API replicas coexist cannot reject a token minted
# by a replica that has not yet been replaced. These are never issued.
LEGACY_PERMISSION_ALIASES: Mapping[str, str] = {
    "department:read": Permission.DEPARTMENTS_READ,
    "department:manage": Permission.DEPARTMENTS_MANAGE,
    "team:read": Permission.TEAMS_READ,
    "team:manage": Permission.TEAMS_MANAGE,
    "client:read": Permission.CLIENTS_READ,
    "client:manage": Permission.CLIENTS_MANAGE,
    "project:read": Permission.PROJECTS_READ,
    "project:manage": Permission.PROJECTS_MANAGE,
    "professional:read:self": Permission.PEOPLE_READ,
    "professional:read:all": Permission.PEOPLE_READ_ALL,
    "professional:intake": Permission.PEOPLE_INTAKE,
    "professional:bulk_import": Permission.PEOPLE_BULK_IMPORT,
    "professional:update": Permission.PEOPLE_UPDATE,
    "onboarding:template:read": Permission.ONBOARDING_TEMPLATES_READ,
    "onboarding:template:manage": Permission.ONBOARDING_TEMPLATES_MANAGE,
    "onboarding:run:read:self": Permission.ONBOARDING_RUNS_READ,
    "onboarding:run:read:all": Permission.ONBOARDING_RUNS_READ_ALL,
    "onboarding:run:create": Permission.ONBOARDING_RUNS_CREATE,
    "onboarding:item:complete:self": Permission.ONBOARDING_ITEMS_COMPLETE,
    "onboarding:item:update:any": Permission.ONBOARDING_ITEMS_MANAGE,
    "assignment:read:self": Permission.ASSIGNMENTS_READ,
    "assignment:read:all": Permission.ASSIGNMENTS_READ_ALL,
    "assignment:allocate": Permission.ASSIGNMENTS_ALLOCATE,
    "assignment:update": Permission.ASSIGNMENTS_UPDATE,
    "access:request:read:self": Permission.ACCESS_READ,
    "access:request:read:all": Permission.ACCESS_READ_ALL,
    "access:request:create:self": Permission.ACCESS_REQUEST,
    "access:request:create:any": Permission.ACCESS_REQUEST_ANY,
    "access:request:approve": Permission.ACCESS_APPROVE,
    "access:request:provision": Permission.ACCESS_PROVISION,
    "access:request:revoke": Permission.ACCESS_REVOKE,
    "access:integration:manage": Permission.INTEGRATIONS_MANAGE,
    "user:manage": Permission.USERS_MANAGE,
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
    service layer evaluates a resource rule outside the HTTP pipeline).
    """

    user_id: Optional[uuid.UUID] = None
    tenant_id: Optional[uuid.UUID] = None
    role: Optional[str] = None
    scopes: FrozenSet[str] = frozenset()
    lead_team_ids: FrozenSet[uuid.UUID] = frozenset()
    email: Optional[str] = None
    claims: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_known_role(self) -> bool:
        return self.role in POLICY_MATRIX

    @property
    def is_team_lead(self) -> bool:
        return Scope.TEAM_LEAD in self.scopes


@dataclass(frozen=True)
class PolicyDecision:
    """Outcome of a single in-memory policy evaluation."""

    allowed: bool
    permission: str
    role: Optional[str]
    reason: str
    resource_tenant_id: Optional[uuid.UUID] = None
    resource_team_id: Optional[uuid.UUID] = None
    granted_via: Optional[str] = None
    scope: Optional[str] = None

    def __bool__(self) -> bool:
        return self.allowed

    @property
    def denied(self) -> bool:
        return not self.allowed

    @property
    def via_scope(self) -> bool:
        """True when authority was derived rather than held by the role."""
        return self.granted_via == "scope"


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


def _coerce_uuid_set(values: Any) -> FrozenSet[uuid.UUID]:
    """Normalize an iterable claim value into a frozenset of UUIDs."""
    if not values:
        return frozenset()
    if isinstance(values, (str, bytes, uuid.UUID)):
        values = [values]
    resolved = {uid for uid in (_coerce_uuid(item) for item in values) if uid}
    return frozenset(resolved)


def _coerce_role(value: Any) -> Optional[str]:
    """Normalize a role claim/attribute to its canonical uppercase value."""
    if value is None:
        return None
    raw = getattr(value, "value", value)
    role = str(raw).strip()
    return role.upper() or None


def _coerce_scope(value: Any) -> Optional[str]:
    """Normalize a scope claim/attribute to its canonical lowercase value."""
    if value is None:
        return None
    raw = getattr(value, "value", value)
    scope = str(raw).strip()
    return scope.lower() or None


# =============================================================================
# Policy Engine
# =============================================================================
class PolicyEngine:
    """In-memory authorization engine evaluated entirely against signed claims.

    Thread-safe and immutable. Does not perform database, network or disk I/O.
    """

    def __init__(
        self,
        matrix: Optional[Mapping[str, FrozenSet[str]]] = None,
        scope_matrix: Optional[Mapping[str, FrozenSet[str]]] = None,
        legacy_aliases: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._matrix: Mapping[str, FrozenSet[str]] = (
            dict(matrix) if matrix is not None else dict(POLICY_MATRIX)
        )
        self._scope_matrix: Mapping[str, FrozenSet[str]] = (
            dict(scope_matrix) if scope_matrix is not None else dict(SCOPE_MATRIX)
        )
        self._legacy_aliases: Mapping[str, str] = (
            dict(legacy_aliases)
            if legacy_aliases is not None
            else dict(LEGACY_PERMISSION_ALIASES)
        )

    # -- canonicalisation ----------------------------------------------------
    def resolve_permission(self, permission: str) -> str:
        """Translate legacy permission strings to canonical O-02 identifiers."""
        if not permission:
            return ""
        cleaned = str(permission).strip()
        return self._legacy_aliases.get(cleaned, cleaned)

    # -- subject construction ------------------------------------------------
    def subject_from_claims(self, claims: Mapping[str, Any]) -> PolicySubject:
        """Build a normalized subject directly from verified JWT claims."""
        return PolicySubject(
            user_id=_coerce_uuid(claims.get("sub")),
            tenant_id=_coerce_uuid(claims.get("tenant_id")),
            role=_coerce_role(claims.get("role")),
            scopes=frozenset(
                scope
                for scope in (_coerce_scope(item) for item in (claims.get("scopes") or []))
                if scope
            ),
            lead_team_ids=_coerce_uuid_set(claims.get("lead_teams")),
            email=claims.get("email"),
            claims=dict(claims),
        )

    def subject_from_principal(self, principal: Any) -> PolicySubject:
        """Build a :class:`PolicySubject` from a ``User`` row, claims, or role.

        Services evaluating resource-scoped rules outside the HTTP pipeline pass
        the authenticated ``User`` directly; the role and tenant are still read
        from the in-memory identity, never from an extra permission query. A
        bare role (``UserRole`` or its string value) is also accepted so that
        non-HTTP callers such as state-machine transition guards can resolve
        authority without constructing a principal.
        """
        if isinstance(principal, PolicySubject):
            return principal
        if isinstance(principal, Mapping):
            return self.subject_from_claims(principal)
        if _coerce_role(principal) in self._matrix:
            return PolicySubject(role=_coerce_role(principal))
        claims = getattr(principal, "_policy_claims", None)
        if isinstance(claims, Mapping):
            # Preserve any derived scopes carried by the verified claims.
            return self.subject_from_claims(claims)
        return PolicySubject(
            user_id=_coerce_uuid(getattr(principal, "id", None)),
            tenant_id=_coerce_uuid(getattr(principal, "tenant_id", None)),
            role=_coerce_role(getattr(principal, "role", None)),
            email=getattr(principal, "email", None),
            claims={},
        )

    # -- role authority ------------------------------------------------------
    def permissions_for_role(self, role: Any) -> FrozenSet[str]:
        """Resolve a role's tenant-wide permission set. Pure memory lookup."""
        normalized = _coerce_role(role)
        if normalized is None:
            return frozenset()
        return self._matrix.get(normalized, frozenset())

    def permissions_for_scope(self, scope: Any) -> FrozenSet[str]:
        """Resolve the permissions a derived scope unlocks."""
        normalized = _coerce_scope(scope)
        if normalized is None:
            return frozenset()
        return self._scope_matrix.get(normalized, frozenset())

    def scopes_for(self, principal: Any) -> FrozenSet[str]:
        """Known derived scopes asserted by the subject's signed claims."""
        subject = self.subject_from_principal(principal)
        return frozenset(s for s in subject.scopes if s in self._scope_matrix)

    def permissions_for(self, principal: Any) -> FrozenSet[str]:
        """Resolve the role's tenant-wide permission set for a subject.

        The ``role`` claim is authoritative: the matrix is the single source of
        truth for what a role may do. The embedded ``perms`` claim is a signed
        convenience artefact (surfaced to clients and the audit ledger) and is
        never used to widen authority, so a matrix change takes effect on the
        next request without re-issuing tokens.
        """
        return self.permissions_for_role(self.subject_from_principal(principal).role)

    def effective_permissions(self, principal: Any) -> FrozenSet[str]:
        """Union of role authority and derived-scope authority for a subject.

        Reported for introspection only. :meth:`authorize` remains the
        authoritative gate because it additionally enforces the tenant boundary
        and the scope resource binding.
        """
        subject = self.subject_from_principal(principal)
        permissions = set(self.permissions_for_role(subject.role))
        for scope in self.scopes_for(subject):
            permissions |= self.permissions_for_scope(scope)
        return frozenset(permissions)

    def has_permission(self, principal: Any, permission: str) -> bool:
        """Fast membership test across role and derived-scope authority."""
        subject = self.subject_from_principal(principal)
        if Permission.WILDCARD in self.permissions_for_role(subject.role):
            return True
        if self.resolve_permission(permission) in self.permissions_for_role(
            subject.role
        ):
            return True
        for scope in self.scopes_for(subject):
            if self.resolve_permission(permission) in self.permissions_for_scope(scope):
                return True
        return False

    def has_any_permission(self, principal: Any, permissions: Sequence[str]) -> bool:
        return any(self.has_permission(principal, perm) for perm in permissions)

    def has_all_permissions(self, principal: Any, permissions: Sequence[str]) -> bool:
        return all(self.has_permission(principal, perm) for perm in permissions)

    def has_role(self, principal: Any, *roles: Any) -> bool:
        """Role membership test resolved from the in-memory matrix."""
        subject = self.subject_from_principal(principal)
        return subject.role in {_coerce_role(role) for role in roles if role is not None}

    def has_scope(self, principal: Any, *scopes: Any) -> bool:
        """Derived-scope membership test resolved from the in-memory matrix."""
        held = self.scopes_for(principal)
        return bool(held & {_coerce_scope(scope) for scope in scopes if scope is not None})

    # -- derived scope boundary ---------------------------------------------
    def check_scope_boundary(
        self,
        principal: Any,
        scope: Any,
        resource_team_id: Any = None,
        *,
        permission: str = "",
    ) -> PolicyDecision:
        """Verify a derived-scope grant applies to the resource being touched.

        A resource-bound scope is only honoured when the resource team appears
        in the signed ``lead_teams`` claim. This is what keeps Team Lead
        authority narrower than the Manager authority that overlaps it.
        """
        subject = self.subject_from_principal(principal)
        scope_name = _coerce_scope(scope)
        label = permission or f"scope:{scope_name}"

        if scope_name is None or scope_name not in self.scopes_for(subject):
            return PolicyDecision(
                allowed=False,
                permission=label,
                role=subject.role,
                reason=f"Access denied: derived scope '{scope_name}' is not held.",
                resource_team_id=_coerce_uuid(resource_team_id),
            )

        if scope_name not in RESOURCE_BOUND_SCOPES:
            return PolicyDecision(
                allowed=True,
                permission=label,
                role=subject.role,
                reason=f"Derived scope '{scope_name}' is not resource-bound.",
                scope=scope_name,
                granted_via="scope",
            )

        if not subject.lead_team_ids:
            return PolicyDecision(
                allowed=False,
                permission=label,
                role=subject.role,
                reason=(
                    f"Access denied: derived scope '{scope_name}' carries no "
                    "resource binding."
                ),
                resource_team_id=_coerce_uuid(resource_team_id),
            )

        target = _coerce_uuid(resource_team_id)
        if target is None or target not in subject.lead_team_ids:
            return PolicyDecision(
                allowed=False,
                permission=label,
                role=subject.role,
                reason=(
                    f"Access denied: '{scope_name}' authority does not extend to "
                    "the requested resource."
                ),
                resource_team_id=target,
                scope=scope_name,
                granted_via="scope",
            )

        return PolicyDecision(
            allowed=True,
            permission=label,
            role=subject.role,
            reason=f"Resource lies within derived scope '{scope_name}'.",
            resource_tenant_id=subject.tenant_id,
            resource_team_id=target,
            scope=scope_name,
            granted_via="scope",
        )

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
        resource_team_id: Any = None,
        enforce_tenant_boundary: bool = True,
        enforce_scope_boundary: bool = True,
    ) -> PolicyDecision:
        """Evaluate a permission request entirely in application memory.

        Order of evaluation is deliberate and fail-closed: role validity, then
        tenant boundary, then role permission membership, then derived-scope
        permission membership with its resource binding. Tenant and scope checks
        can never be skipped by holding a broader role.
        """
        subject = self.subject_from_principal(principal)
        canonical = self.resolve_permission(permission)
        tenant_target = _coerce_uuid(resource_tenant_id)
        team_target = _coerce_uuid(resource_team_id)

        if subject.role is None:
            return PolicyDecision(
                allowed=False,
                permission=canonical,
                role=None,
                reason="Access denied: token carries no role claim.",
                resource_tenant_id=tenant_target,
                resource_team_id=team_target,
            )
        if subject.role not in self._matrix:
            return PolicyDecision(
                allowed=False,
                permission=canonical,
                role=subject.role,
                reason=(
                    f"Access denied: role '{subject.role}' is not present in the "
                    "policy matrix."
                ),
                resource_tenant_id=tenant_target,
                resource_team_id=team_target,
            )

        if enforce_tenant_boundary:
            boundary = self.check_tenant_boundary(
                subject, tenant_target, permission=canonical
            )
            if not boundary.allowed:
                return boundary

        role_permissions = self.permissions_for_role(subject.role)
        if Permission.WILDCARD in role_permissions or canonical in role_permissions:
            return PolicyDecision(
                allowed=True,
                permission=canonical,
                role=subject.role,
                reason=f"Role '{subject.role}' grants '{canonical}'.",
                resource_tenant_id=tenant_target,
                resource_team_id=team_target,
                granted_via="role",
            )

        for scope in sorted(self.scopes_for(subject)):
            if canonical not in self.permissions_for_scope(scope):
                continue
            if scope in RESOURCE_BOUND_SCOPES and enforce_scope_boundary:
                scoped = self.check_scope_boundary(
                    subject, scope, team_target, permission=canonical
                )
                if not scoped.allowed:
                    return scoped
                return scoped
            return PolicyDecision(
                allowed=True,
                permission=canonical,
                role=subject.role,
                reason=f"Derived scope '{scope}' grants '{canonical}'.",
                resource_tenant_id=tenant_target,
                resource_team_id=team_target,
                granted_via="scope",
                scope=scope,
            )

        return PolicyDecision(
            allowed=False,
            permission=canonical,
            role=subject.role,
            reason=(
                f"Access denied: role '{subject.role}' does not grant "
                f"'{canonical}'."
            ),
            resource_tenant_id=tenant_target,
            resource_team_id=team_target,
        )

    def can(
        self,
        principal: Any,
        permission: str,
        *,
        resource_tenant_id: Any = None,
        resource_team_id: Any = None,
        enforce_tenant_boundary: bool = True,
        enforce_scope_boundary: bool = True,
    ) -> bool:
        """Boolean convenience wrapper around :meth:`authorize`."""
        return bool(
            self.authorize(
                principal,
                permission,
                resource_tenant_id=resource_tenant_id,
                resource_team_id=resource_team_id,
                enforce_tenant_boundary=enforce_tenant_boundary,
                enforce_scope_boundary=enforce_scope_boundary,
            )
        )

    def enforce(
        self,
        principal: Any,
        permission: str,
        *,
        resource_tenant_id: Any = None,
        resource_team_id: Any = None,
        enforce_tenant_boundary: bool = True,
        enforce_scope_boundary: bool = True,
    ) -> PolicyDecision:
        """Authorize or raise :class:`PolicyDeniedError` (fail closed)."""
        decision = self.authorize(
            principal,
            permission,
            resource_tenant_id=resource_tenant_id,
            resource_team_id=resource_team_id,
            enforce_tenant_boundary=enforce_tenant_boundary,
            enforce_scope_boundary=enforce_scope_boundary,
        )
        if not decision.allowed:
            raise PolicyDeniedError(decision)
        return decision

    # -- team lead helpers --------------------------------------------------
    def is_team_lead_of(self, principal: Any, team_id: Any) -> bool:
        """Whether the subject's derived ``team_lead`` scope covers ``team_id``."""
        subject = self.subject_from_principal(principal)
        if not subject.is_team_lead:
            return False
        target = _coerce_uuid(team_id)
        return target is not None and target in subject.lead_team_ids

    # -- token issuance support --------------------------------------------
    def permissions_for_token(self, role: Any) -> Sequence[str]:
        """Sorted role permission list to embed as the signed ``perms`` claim."""
        return sorted(self.permissions_for_role(role))


#: Process-wide engine singleton. Immutable and safe to share across threads.
policy_engine = PolicyEngine()
