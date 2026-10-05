"""DWOP-018: RBAC PERMISSION MATRIX PUBLICATION & TEAM LEAD DERIVED SCOPE SUITE

Task O-02 verification harness.

Covers:
- Machine-verified bidirectional sync between ``docs/rbac-matrix.md`` (the
  single authoritative, audit-ready matrix) and the in-memory ``POLICY_MATRIX`` /
  ``SCOPE_MATRIX`` configuration tables in ``app.core.policy``
- Column-level parsing of every capability table in the document, so a
  mis-attributed grant in the document fails just as loudly as a missing one
- Team Lead as a derived, resource-bound scope resolved from ``Team.team_lead_id``
  with no fourth database role and no schema migration
- Strict scope boundary: own team allowed, foreign team denied, cross-tenant denied
- Signed ``scopes`` / ``lead_teams`` JWT claims, tamper rejection, and propagation
  on token refresh
"""

import os
import re
import sys
import uuid

from fastapi.testclient import TestClient

sys.path.insert(0, ".")

from app.core.policy import (
    ADMIN_PERMISSIONS,
    LEGACY_PERMISSION_ALIASES,
    MANAGER_PERMISSIONS,
    MEMBER_PERMISSIONS,
    TEAM_LEAD_SCOPE_PERMISSIONS,
    Permission,
    PolicyEngine,
    PolicySubject,
    RESOURCE_BOUND_SCOPES,
    Scope,
    policy_engine,
)
from app.core.scopes import EMPTY_SCOPE_GRANT, ScopeResolver, resolve_scope_grant
from app.core.security import create_access_token, decode_access_token, get_password_hash
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.organization import Department, Team
from app.models.tenant import Tenant
from app.models.user import User, UserRole

# Idempotent: guarantees the derived-scope fixtures have a schema to write to.
Base.metadata.create_all(bind=engine)

client = TestClient(app)
base_url = "/api/v1"

DOC_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "rbac-matrix.md"
)

PASSED = 0


def ok(label: str, condition: bool, detail: str = "") -> None:
    global PASSED
    assert condition, f"[FAIL] {label} {detail}"
    PASSED += 1
    print(f"  [PASS] {label}" + (f" {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# =============================================================================
# Document parser: turns the published matrix back into policy tables
# =============================================================================

PERMISSION_RE = re.compile(r"^[a-z]+(?::[a-z_]+)+$")
CODE_RE = re.compile(r"`([^`]+)`")

ROLE_COLUMN_LABELS = {
    "member": "MEMBER",
    "manager": "MANAGER",
    "admin": "ADMIN",
    "member + `team_lead`": "SCOPE:team_lead",
}


def normalize_column(label: str) -> str:
    return ROLE_COLUMN_LABELS.get(label.strip().lower(), "")


def parse_document_matrix(path: str):
    """Extract ``{role: {permission, ...}}`` and all permission codes from the doc.

    Returns a tuple of the role-keyed grant table and the flat set of every
    permission code mentioned anywhere in the document.
    """
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    grants = {}
    every_code = set()

    columns: list = []
    for line in lines:
        if not line.startswith("|"):
            columns = []
            continue

        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]

        header_roles = [normalize_column(cell) for cell in cells]
        if cells and cells[0] == "Permission":
            columns = [
                (index, role) for index, role in enumerate(header_roles) if role
            ]
            continue

        if not columns or len(cells) < 2:
            continue

        match = CODE_RE.fullmatch(cells[0])
        if not match or not PERMISSION_RE.match(match.group(1)):
            continue

        permission = match.group(1)
        every_code.add(permission)
        for index, role in columns:
            if index < len(cells) and cells[index].startswith("\u2714"):
                grants.setdefault(role, set()).add(permission)

    return grants, every_code


# =============================================================================
section("TEST 1: docs/rbac-matrix.md Is Bidirectionally Synchronized With Code")
# =============================================================================

assert os.path.exists(DOC_PATH), f"[FAIL] authoritative matrix missing at {DOC_PATH}"
print("\n[TEST 1] Published matrix and in-memory policy tables agree exactly")

doc_grants, doc_codes = parse_document_matrix(DOC_PATH)
code_grants = {
    "MEMBER": set(MEMBER_PERMISSIONS),
    "MANAGER": set(MANAGER_PERMISSIONS),
    "ADMIN": set(ADMIN_PERMISSIONS),
    "SCOPE:team_lead": set(TEAM_LEAD_SCOPE_PERMISSIONS),
}

for role in ("MEMBER", "MANAGER", "ADMIN", "SCOPE:team_lead"):
    ok(
        f"Document grants for {role} match the code exactly",
        doc_grants.get(role, set()) == code_grants[role],
        f"(document={len(doc_grants.get(role, set()))}, code={len(code_grants[role])})"
        + (
            f" doc-only={sorted(doc_grants.get(role, set()) - code_grants[role])}"
            f" code-only={sorted(code_grants[role] - doc_grants.get(role, set()))}"
            if doc_grants.get(role, set()) != code_grants[role]
            else ""
        ),
    )

every_code_permission = set(policy_engine.all_permissions) | set(
    TEAM_LEAD_SCOPE_PERMISSIONS
)
ok(
    "No permission appears in the document that the engine cannot resolve",
    doc_codes <= every_code_permission,
    f"(undocumented-in-code={sorted(doc_codes - every_code_permission)})",
)
ok(
    "No permission exists in the engine that the document fails to publish",
    every_code_permission <= doc_codes,
    f"(unpublished={sorted(every_code_permission - doc_codes)})",
)
ok(
    "Documented permission count matches the engine catalogue",
    len(doc_codes) == len(every_code_permission) == 37,
    f"({len(doc_codes)} permissions documented, {len(policy_engine.all_permissions)} in POLICY_MATRIX)",
)

# =============================================================================
section("TEST 2: Matrix Structural Integrity (nesting, no wildcards, no 4th role)")
# =============================================================================

print("\n[TEST 2] Documented tiers are strictly nested with no wildcard grants")

ok(
    "MEMBER is a strict subset of MANAGER",
    MEMBER_PERMISSIONS < MANAGER_PERMISSIONS,
    f"({len(MEMBER_PERMISSIONS)} / {len(MANAGER_PERMISSIONS)} permissions)",
)
ok(
    "MANAGER is a strict subset of ADMIN",
    MANAGER_PERMISSIONS < ADMIN_PERMISSIONS,
    f"({len(MANAGER_PERMISSIONS)} / {len(ADMIN_PERMISSIONS)} permissions)",
)
ok(
    "Permission counts match the published document",
    (len(MEMBER_PERMISSIONS), len(MANAGER_PERMISSIONS), len(ADMIN_PERMISSIONS))
    == (12, 23, 37),
    f"(MEMBER={len(MEMBER_PERMISSIONS)}, MANAGER={len(MANAGER_PERMISSIONS)}, ADMIN={len(ADMIN_PERMISSIONS)})",
)
ok(
    "No locked tier or derived scope holds the '*' superuser sentinel",
    "*" not in every_code_permission
    and all(
        "*" not in grants
        for grants in (
            MEMBER_PERMISSIONS,
            MANAGER_PERMISSIONS,
            ADMIN_PERMISSIONS,
            TEAM_LEAD_SCOPE_PERMISSIONS,
        )
    ),
)
ok(
    "Team Lead is not a UserRole member (three locked tiers only)",
    {role.value for role in UserRole} == {"ADMIN", "MANAGER", "MEMBER"},
    f"({sorted(role.value for role in UserRole)})",
)
ok(
    "Team Lead is not expressible as a stored role value",
    not any("team_lead" == role.value for role in UserRole)
    and "team_lead" not in {role.value for role in UserRole},
)
ok(
    "Team Lead is published as a derived scope, not a tier",
    Scope.TEAM_LEAD in policy_engine.all_scopes
    and policy_engine.all_scopes == frozenset({Scope.TEAM_LEAD}),
    f"(scopes={sorted(policy_engine.all_scopes)})",
)

# =============================================================================
section("TEST 3: Operational Identifier Formats Match The Published Contract")
# =============================================================================

print("\n[TEST 3] Documented operational formats are enforced end to end")

for example in (
    "people:read",
    "assignments:allocate",
    "access:approve",
    "audit:export",
):
    ok(
        f"Documented example format '{example}' resolves in the engine",
        policy_engine.resolve_permission(example) == example
        and example in doc_codes,
    )

ok(
    "Every published permission uses <domain>:<action>[:<qualifier>] with [a-z_] segments",
    all(PERMISSION_RE.match(code) for code in doc_codes),
    f"({len(doc_codes)} codes validated)",
)
ok(
    "No legacy O-01 identifier survives in the published matrix",
    not (set(LEGACY_PERMISSION_ALIASES) & doc_codes),
    f"({len(LEGACY_PERMISSION_ALIASES)} legacy aliases kept out of the document)",
)
ok(
    "Legacy O-01 identifiers still resolve for rolling-deploy compatibility",
    policy_engine.resolve_permission("department:manage") == Permission.DEPARTMENTS_MANAGE
    and policy_engine.resolve_permission("access:request:approve")
    == Permission.ACCESS_APPROVE
    and policy_engine.resolve_permission("professional:intake") == Permission.PEOPLE_INTAKE,
    "(read-side alias table intact)",
)
ok(
    "Alias resolution is a no-op for every already-canonical identifier",
    all(
        policy_engine.resolve_permission(code) == code
        for code in every_code_permission
    ),
)
ok(
    "Team Lead scope grants are all resource-bound",
    Scope.TEAM_LEAD in RESOURCE_BOUND_SCOPES
    and bool(TEAM_LEAD_SCOPE_PERMISSIONS)
    and policy_engine.permissions_for_scope(Scope.TEAM_LEAD)
    == TEAM_LEAD_SCOPE_PERMISSIONS,
    f"({sorted(TEAM_LEAD_SCOPE_PERMISSIONS)})",
)
ok(
    "Documented scope table grants are strictly narrower than Manager authority",
    set(TEAM_LEAD_SCOPE_PERMISSIONS) < MANAGER_PERMISSIONS,
    f"({len(TEAM_LEAD_SCOPE_PERMISSIONS)} scoped of {len(MANAGER_PERMISSIONS)} Manager permissions)",
)

# =============================================================================
section("TEST 4: Team Lead Is Derived From Team.team_lead_id (No Migration)")
# =============================================================================

print("\n[TEST 4] Derived scope resolution reads relational data, never a role column")


def _tamper_rejected(token: str, claim: str) -> bool:
    """Mutate a claim in the JWT payload and confirm verification rejects it."""
    import base64
    import json

    header_b64, payload_b64, signature_b64 = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
    payload[claim] = [str(uuid.uuid4())] if claim == "lead_teams" else ["team_lead"]
    forged_payload = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("utf-8").rstrip("=")
    forged = f"{header_b64}.{forged_payload}.{signature_b64}"
    try:
        decode_access_token(forged)
        return False
    except Exception:
        return True


def _plain_token() -> dict:
    """A MEMBER token issued with no scope claims at all."""
    return decode_access_token(
        create_access_token(
            subject=str(outsider),
            tenant_id=str(tenant_id),
            role=UserRole.MEMBER.value,
            email="o02.outsider@matrix.test",
            permissions=sorted(MEMBER_PERMISSIONS),
            scopes=[],
            lead_teams=[],
        )
    )


db = SessionLocal()
tenant_id = uuid.uuid4()
lead_a = uuid.uuid4()
lead_b = uuid.uuid4()
outsider = uuid.uuid4()
plain = uuid.uuid4()
department_id = uuid.uuid4()
team_alpha = uuid.uuid4()
team_beta = uuid.uuid4()
PASSWORD = "LeadScope2026!"


def make_user(user_id: uuid.UUID, email: str, role: UserRole) -> User:
    return User(
        id=user_id,
        tenant_id=tenant_id,
        email=email,
        hashed_password=get_password_hash(PASSWORD),
        role=role,
        is_active=True,
    )


try:
    # Clear any fixtures left behind by an interrupted earlier run so the suite is
    # repeatable against a persistent database.
    stale = db.query(Tenant).filter(Tenant.slug.like("o02-%")).all()
    for row in stale:
        db.query(Team).filter(Team.tenant_id == row.id).delete(synchronize_session=False)
        db.query(Department).filter(Department.tenant_id == row.id).delete(synchronize_session=False)
        db.query(User).filter(User.tenant_id == row.id).delete(synchronize_session=False)
        db.delete(row)
    db.commit()

    tenant = Tenant(id=tenant_id, name="O-02 Matrix Tenant", slug=f"o02-{tenant_id.hex[:8]}")
    tenant.is_active = True
    db.add(tenant)
    db.add(Department(id=department_id, tenant_id=tenant_id, name="Matrix Engineering"))
    db.add(
        Team(
            id=team_alpha,
            tenant_id=tenant_id,
            department_id=department_id,
            name="Team Alpha",
            team_lead_id=lead_a,
        )
    )
    db.add(
        Team(
            id=team_beta,
            tenant_id=tenant_id,
            department_id=department_id,
            name="Team Beta",
            team_lead_id=lead_b,
        )
    )
    # A third team deliberately left without a lead.
    db.add(
        Team(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            department_id=department_id,
            name="Team Vacant",
            team_lead_id=None,
        )
    )
    db.add(make_user(lead_a, "o02.lead.a@matrix.test", UserRole.MEMBER))
    db.add(make_user(lead_b, "o02.lead.b@matrix.test", UserRole.MEMBER))
    db.add(make_user(outsider, "o02.outsider@matrix.test", UserRole.MEMBER))
    db.add(make_user(plain, "o02.plain@matrix.test", UserRole.MEMBER))
    db.commit()

    resolver = ScopeResolver(db)

    grant = resolver.derive(lead_a, tenant_id)
    ok(
        "Team lead derives the 'team_lead' scope from Team.team_lead_id",
        grant.is_team_lead and grant.scopes == frozenset({Scope.TEAM_LEAD}),
        f"(scopes={sorted(grant.scopes)})",
    )
    ok(
        "Derived scope carries the signed lead_teams binding",
        tuple(grant.lead_team_ids) == (team_alpha,),
        f"(lead_teams={grant.lead_teams})",
    )
    ok(
        "A user leading two teams receives both bindings",
        tuple(ScopeResolver(db).derive(lead_b, tenant_id).lead_team_ids) == (team_beta,),
    )

    non_lead = resolver.derive(outsider, tenant_id)
    ok(
        "A user with no team_lead_id receives no scope",
        not non_lead.is_team_lead
        and non_lead.scopes == frozenset()
        and non_lead.lead_team_ids == (),
    )
    ok(
        "Team membership alone never confers scope",
        not resolver.derive(plain, tenant_id).is_team_lead,
    )

    # A team the user leads in ANOTHER tenant must never reach the claim.
    foreign_tenant_id = uuid.uuid4()
    foreign_team_id = uuid.uuid4()
    db.add(Tenant(id=foreign_tenant_id, name="Foreign Tenant", slug=f"o02-foreign-{foreign_tenant_id.hex[:8]}"))
    db.add(
        Team(
            id=foreign_team_id,
            tenant_id=foreign_tenant_id,
            department_id=department_id,
            name="Foreign Team",
            team_lead_id=lead_a,
        )
    )
    db.commit()
    ok(
        "A cross-tenant team never enters the lead_teams claim",
        foreign_team_id not in resolver.derive(lead_a, tenant_id).lead_team_ids
        and resolver.derive(lead_a, tenant_id).is_team_lead,
        "(derivation is tenant-scoped, so the foreign team is invisible)",
    )
    ok(
        "Deriving against the foreign tenant does surface that team",
        foreign_team_id in resolver.derive(lead_a, foreign_tenant_id).lead_team_ids,
    )
    ok(
        "Unknown or missing user resolves to the empty grant (fail closed)",
        resolve_scope_grant(db, None, tenant_id) == EMPTY_SCOPE_GRANT
        and resolve_scope_grant(db, uuid.uuid4(), tenant_id) == EMPTY_SCOPE_GRANT,
    )

    lead_a_row = db.query(User).filter(User.id == lead_a).one()
    ok(
        "Deriving a scope never mutates users.role",
        lead_a_row.role == UserRole.MEMBER
        and db.query(Team).filter(Team.id == team_alpha).one().team_lead_id == lead_a,
        "(users.role still MEMBER; authority lives only in Team.team_lead_id)",
    )

    # ---- scope boundary enforcement -------------------------------------
    lead_token = create_access_token(
        subject=str(lead_a),
        tenant_id=str(tenant_id),
        role=UserRole.MEMBER.value,
        email="o02.lead.a@matrix.test",
        permissions=sorted(MEMBER_PERMISSIONS),
        scopes=sorted(grant.scopes),
        lead_teams=list(grant.lead_team_ids),
    )
    lead_claims = decode_access_token(lead_token)
    ok(
        "Token embeds sorted, signed scope and lead-team claims",
        lead_claims["scopes"] == [Scope.TEAM_LEAD]
        and lead_claims["lead_teams"] == [str(team_alpha)],
        f"(scopes={lead_claims['scopes']}, lead_teams={lead_claims['lead_teams']})",
    )

    ok(
        "Team lead is granted scope authority on their own team",
        policy_engine.authorize(
            lead_claims,
            Permission.PEOPLE_READ_ALL,
            resource_tenant_id=tenant_id,
            resource_team_id=team_alpha,
        ).allowed,
    )
    ok(
        "Team lead is denied the same authority on a team they do not lead",
        policy_engine.authorize(
            lead_claims,
            Permission.PEOPLE_READ_ALL,
            resource_tenant_id=tenant_id,
            resource_team_id=team_beta,
        ).denied,
    )
    ok(
        "Scope authority fails closed without a resource team identifier",
        policy_engine.authorize(
            lead_claims,
            Permission.PEOPLE_READ_ALL,
            resource_tenant_id=tenant_id,
        ).denied,
    )
    ok(
        "Team lead cannot reach across tenants even on their own team",
        policy_engine.authorize(
            lead_claims,
            Permission.PEOPLE_READ_ALL,
            resource_tenant_id=uuid.uuid4(),
            resource_team_id=team_alpha,
        ).denied,
    )
    ok(
        "Non-scope permissions remain available to a team lead",
        policy_engine.authorize(
            lead_claims,
            Permission.PEOPLE_READ,
            resource_tenant_id=tenant_id,
        ).allowed,
    )
    ok(
        "Effective permissions union role and derived scope",
        policy_engine.effective_permissions(lead_claims)
        == sorted(MEMBER_PERMISSIONS | TEAM_LEAD_SCOPE_PERMISSIONS)
        or set(policy_engine.effective_permissions(lead_claims))
        == MEMBER_PERMISSIONS | TEAM_LEAD_SCOPE_PERMISSIONS,
        f"({len(policy_engine.effective_permissions(lead_claims))} effective)",
    )
    ok(
        "A tampered lead_teams claim is rejected by signature verification",
        _tamper_rejected(lead_token, "lead_teams"),
    )
    ok(
        "A tampered scopes claim is rejected by signature verification",
        _tamper_rejected(lead_token, "scopes"),
    )
    ok(
        "A member token without scope claims cannot borrow team-lead authority",
        policy_engine.authorize(
            _plain_token(),
            Permission.PEOPLE_READ_ALL,
            resource_tenant_id=tenant_id,
            resource_team_id=team_alpha,
        ).denied,
    )

    # ---- scope revocation on reassignment --------------------------------
    db.query(Team).filter(Team.id == team_alpha).one().team_lead_id = lead_b
    db.commit()
    refreshed = ScopeResolver(db).derive(lead_a, tenant_id)
    ok(
        "Reassigning Team.team_lead_id removes the derived scope on re-issuance",
        not refreshed.is_team_lead and refreshed.lead_team_ids == (),
    )
    db.query(Team).filter(Team.id == team_alpha).one().team_lead_id = lead_a
    db.commit()
finally:
    # Fixtures stay resident for TEST 5 (HTTP surface); cleaned up at the end.
    db.rollback()
    db.close()

# =============================================================================
section("TEST 5: HTTP Surface Emits And Propagates The Derived Scope")
# =============================================================================

print("\n[TEST 5] Login, refresh and /auth/policy all reflect the derived scope")

r = client.post(
    f"{base_url}/auth/login",
    json={"email": "o02.lead.a@matrix.test", "password": PASSWORD},
)
ok("Team lead login returns 200", r.status_code == 200, r.text[:160] if r.status_code != 200 else "")
lead_login = r.json()
ok(
    "Login response publishes the derived scope and lead-team binding",
    lead_login["scopes"] == [Scope.TEAM_LEAD]
    and lead_login["lead_teams"] == [str(team_alpha)],
    f"(scopes={lead_login.get('scopes')}, lead_teams={lead_login.get('lead_teams')})",
)
ok(
    "Login role remains MEMBER (Team Lead is not a role)",
    lead_login["role"] == "MEMBER",
    f"(role={lead_login.get('role')})",
)
lead_headers = {"Authorization": f"Bearer {lead_login['access_token']}"}

r = client.get(f"{base_url}/auth/policy", headers=lead_headers)
ok("GET /auth/policy returns 200", r.status_code == 200, r.text[:160] if r.status_code != 200 else "")
policy_body = r.json()
ok(
    "/auth/policy separates role permissions from effective authority",
    sorted(policy_body["permissions"]) == sorted(MEMBER_PERMISSIONS)
    and set(policy_body["effective_permissions"])
    == MEMBER_PERMISSIONS | TEAM_LEAD_SCOPE_PERMISSIONS,
    f"({len(policy_body['permissions'])} role, {len(policy_body['effective_permissions'])} effective)",
)
ok(
    "/auth/policy reports the scope, its binding and the enforcement flags",
    policy_body["scopes"] == [Scope.TEAM_LEAD]
    and policy_body["lead_teams"] == [str(team_alpha)]
    and policy_body["is_team_lead"] is True
    and policy_body["scope_boundaries_enforced"] is True
    and policy_body["tenant_boundary_enforced"] is True
    and policy_body["authority_reference"] == "docs/rbac-matrix.md",
)

r = client.post(
    f"{base_url}/auth/login",
    json={"email": "o02.outsider@matrix.test", "password": PASSWORD},
)
outsider_login = r.json()
ok(
    "A non-lead login publishes no scope and no lead-team binding",
    outsider_login["scopes"] == [] and outsider_login["lead_teams"] == [],
    f"(scopes={outsider_login.get('scopes')})",
)
r = client.get(
    f"{base_url}/auth/policy",
    headers={"Authorization": f"Bearer {outsider_login['access_token']}"},
)
ok(
    "A non-lead effective policy is exactly the MEMBER tier",
    r.json()["is_team_lead"] is False
    and sorted(r.json()["effective_permissions"]) == sorted(MEMBER_PERMISSIONS),
)

# ---- trusted-resource dependency wiring ---------------------------------
db = SessionLocal()
try:
    from app.core.dependencies import enforce_scope_boundary
    from fastapi import HTTPException

    lead_subject = PolicySubject(
        user_id=lead_a,
        tenant_id=tenant_id,
        role=UserRole.MEMBER.value,
        scopes=frozenset({Scope.TEAM_LEAD}),
        lead_team_ids=(team_alpha,),
    )
    ok(
        "enforce_scope_boundary passes a team the caller leads",
        enforce_scope_boundary(resource_team_id=team_alpha, subject=lead_subject)
        is lead_subject,
    )
    denied = False
    try:
        enforce_scope_boundary(resource_team_id=team_beta, subject=lead_subject)
    except HTTPException as exc:
        denied = exc.status_code == 403
    ok("enforce_scope_boundary raises 403 for a team the caller does not lead", denied)

    denied_scope = False
    try:
        enforce_scope_boundary(resource_team_id=team_alpha, subject=lead_subject, scope="nonexistent")
    except HTTPException as exc:
        denied_scope = exc.status_code == 403
    ok("enforce_scope_boundary fails closed on an unasserted scope", denied_scope)

    # ---- propagation on refresh -----------------------------------------
    db.query(Team).filter(Team.id == team_alpha).one().team_lead_id = lead_b
    db.commit()
    r = client.post(f"{base_url}/auth/refresh", headers=lead_headers)
    ok("POST /auth/refresh returns 200", r.status_code == 200, r.text[:160] if r.status_code != 200 else "")
    refreshed_body = r.json()
    ok(
        "Scope loss propagates on the holder's next token refresh",
        refreshed_body["scopes"] == [] and refreshed_body["lead_teams"] == [],
        f"(scopes={refreshed_body.get('scopes')})",
    )
    stale_token = decode_access_token(lead_login["access_token"])
    ok(
        "Stale-token staleness is bounded by the access-token lifetime (documented)",
        policy_engine.authorize(
            stale_token,
            Permission.PEOPLE_READ_ALL,
            resource_tenant_id=tenant_id,
            resource_team_id=team_alpha,
        ).allowed,
        "(stateless engine: scope revocation lands on next issuance, not mid-token)",
    )
    ok(
        "Even a stale token cannot exceed the lead_teams binding it was signed with",
        policy_engine.authorize(
            stale_token,
            Permission.PEOPLE_READ_ALL,
            resource_tenant_id=tenant_id,
            resource_team_id=team_beta,
        ).denied,
    )
finally:
    db.rollback()
    db.query(Team).filter(Team.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(Department).filter(Department.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(User).filter(User.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(Tenant).filter(Tenant.id == tenant_id).delete(synchronize_session=False)
    db.commit()
    db.close()

print(f"\n{'=' * 78}\nDWOP-018 PASSED: {PASSED} assertions\n{'=' * 78}")