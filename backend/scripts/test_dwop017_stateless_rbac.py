"""DWOP-017: STATELESS RBAC POLICY ENGINE & HYBRID OFFBOARDING GUARD SUITE

Task O-01 verification harness (ADR-002).

Covers:
- PolicyEngine in-memory matrix resolution (no I/O, fail-closed, frozen snapshot)
- Signed JWT claim payload (role / tenant_id / perms) + tamper rejection
- Single-query hybrid offboarding guard (User.is_active AND Tenant.is_active)
- Instant revocation of offboarded professionals and suspended tenants
- Tenant boundary enforcement surviving a broadened role
"""

import sys
import time
import uuid

from fastapi.testclient import TestClient

sys.path.insert(0, ".")

from app.core.policy import (
    ADMIN_PERMISSIONS,
    MANAGER_PERMISSIONS,
    MEMBER_PERMISSIONS,
    Permission,
    PolicyDeniedError,
    PolicyEngine,
    policy_engine,
)
from app.core.security import create_access_token, decode_access_token
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.core.database import SessionLocal

client = TestClient(app)
base_url = "/api/v1"

PASSED = 0


def ok(label: str, condition: bool, detail: str = "") -> None:
    global PASSED
    assert condition, f"[FAIL] {label} {detail}"
    PASSED += 1
    print(f"  [PASS] {label}" + (f" {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def login(email: str, password: str):
    return client.post(
        f"{base_url}/auth/login", json={"email": email, "password": password}
    )


ADMIN = ("admin@azm-nexus.com", "Admin123!")
MANAGER = ("manager@azm-nexus.com", "Manager123!")
MEMBER = ("member@azm-nexus.com", "Member123!")


# =============================================================================
section("TEST 1: In-Memory Policy Matrix Resolution (zero I/O)")
# =============================================================================
print("\n[TEST 1] PolicyEngine resolves permissions from application memory only")

ok(
    "MEMBER matrix is self-service scoped only",
    not policy_engine.has_permission("MEMBER", Permission.DEPARTMENTS_MANAGE)
    and not policy_engine.has_permission("MEMBER", Permission.AUDIT_READ),
)
ok(
    "MANAGER matrix inherits MEMBER capabilities",
    MEMBER_PERMISSIONS.issubset(MANAGER_PERMISSIONS)
    and policy_engine.has_permission("MANAGER", Permission.ASSIGNMENTS_ALLOCATE),
)
ok(
    "ADMIN matrix inherits MANAGER capabilities",
    MANAGER_PERMISSIONS.issubset(ADMIN_PERMISSIONS)
    and policy_engine.has_permission("ADMIN", Permission.AUDIT_EXPORT),
)
ok(
    "Matrix snapshot is immutable",
    isinstance(policy_engine.matrix["ADMIN"], frozenset),
    f"({len(policy_engine.all_permissions)} permissions catalogued)",
)
ok(
    "Role resolution is case-insensitive",
    policy_engine.has_permission("admin", Permission.USERS_MANAGE)
    and policy_engine.has_permission(UserRole.ADMIN, Permission.USERS_MANAGE),
)

# Sub-millisecond resolution budget.
iterations = 20000
start = time.perf_counter()
for _ in range(iterations):
    policy_engine.authorize(
        {"sub": str(uuid.uuid4()), "tenant_id": str(uuid.uuid4()), "role": "MANAGER"},
        Permission.ASSIGNMENTS_ALLOCATE,
        resource_tenant_id=uuid.uuid4(),
    )
elapsed_ms = (time.perf_counter() - start) * 1000
per_call_us = (elapsed_ms / iterations) * 1000
ok(
    "Policy resolution is sub-millisecond",
    per_call_us < 1000,
    f"(avg {per_call_us:.2f} us/call over {iterations:,} evaluations)",
)

# =============================================================================
section("TEST 2: Fail-Closed Evaluation")
# =============================================================================
print("\n[TEST 2] Engine fails closed on missing/unknown role and tenant drift")

ok(
    "Missing role claim denies",
    policy_engine.authorize({"sub": "x", "tenant_id": None, "role": None}, Permission.TENANT_READ).denied,
)
ok(
    "Unknown role denies",
    policy_engine.authorize(
        {"sub": "x", "tenant_id": str(uuid.uuid4()), "role": "SUPERUSER"},
        Permission.TENANT_READ,
        resource_tenant_id=uuid.uuid4(),
    ).denied,
)
ok(
    "Missing tenant claim denies",
    policy_engine.authorize({"sub": "x", "tenant_id": None, "role": "ADMIN"}, Permission.AUDIT_READ).denied,
)
try:
    policy_engine.enforce(
        {"sub": "x", "tenant_id": str(uuid.uuid4()), "role": "MEMBER"},
        Permission.DEPARTMENTS_MANAGE,
        resource_tenant_id=uuid.uuid4(),
    )
    raise AssertionError("enforce() should have raised PolicyDeniedError")
except PolicyDeniedError as exc:
    ok("enforce() raises PolicyDeniedError", True, f"-> {exc.decision.reason}")

# Custom (non-role) principals must not inherit authority.
sentinel = PolicyEngine({"AUDITOR": frozenset({Permission.AUDIT_READ})})
ok(
    "Isolated engine honours only its own matrix",
    sentinel.has_permission("AUDITOR", Permission.AUDIT_READ)
    and not sentinel.has_permission("ADMIN", Permission.AUDIT_READ),
)

# =============================================================================
section("TEST 3: Tenant Boundary Is Strictly Retained")
# =============================================================================
print("\n[TEST 3] Cross-tenant access denied even for ADMIN (role breadth != isolation)")

tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
admin_claims = {
    "sub": str(uuid.uuid4()),
    "tenant_id": str(tenant_a),
    "role": "ADMIN",
}
ok(
    "Same-tenant ADMIN allowed",
    policy_engine.can(
        admin_claims, Permission.AUDIT_READ, resource_tenant_id=tenant_a
    ),
)
cross = policy_engine.authorize(
    admin_claims, Permission.AUDIT_READ, resource_tenant_id=tenant_b
)
ok(
    "Cross-tenant ADMIN denied",
    cross.denied and "cross-tenant" in cross.reason,
    f"-> {cross.reason}",
)

# =============================================================================
section("TEST 4: Signed Token Claim Payload")
# =============================================================================
print("\n[TEST 4] Access JWT embeds signed role, tenant_id and permissions claims")

r = login(*ADMIN)
assert r.status_code == 200, f"Admin login failed: {r.text}"
admin_body = r.json()
admin_token = admin_body["access_token"]
claims = decode_access_token(admin_token)

ok("role claim present and verified", claims.get("role") == "ADMIN", f"-> {claims.get('role')}")
ok(
    "tenant_id claim present and verified",
    claims.get("tenant_id") == str(admin_body["tenant_id"]),
)
ok(
    "permissions claim present and verified",
    claims.get("perms") == sorted(ADMIN_PERMISSIONS),
    f"({len(claims.get('perms', []))} permissions embedded)",
)
ok("issuer/audience claims bound", claims.get("iss") == "dwop-platform" and claims.get("aud") == "dwop-api")
ok("jti claim present for token identity", bool(claims.get("jti")))

member_body = login(*MEMBER).json()
member_claims = decode_access_token(member_body["access_token"])
ok(
    "MEMBER token carries only MEMBER permissions",
    member_claims.get("perms") == sorted(MEMBER_PERMISSIONS)
    and member_claims.get("perms") != admin_claims.get("perms"),
    f"({len(member_claims.get('perms', []))} permissions embedded)",
)

# Tamper detection: privilege escalation via payload editing must fail.
forged_token = (
    create_access_token(
        subject=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        role="MEMBER",
        email="attacker@evil.test",
    ).rsplit(".", 1)[0]
    + "." + admin_token.rsplit(".", 1)[1]
)
r = client.get(f"{base_url}/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
ok("Tampered signature rejected with 401", r.status_code == 401, f"-> {r.status_code}")

escalated = create_access_token(
    subject=claims["sub"],
    tenant_id=claims["tenant_id"],
    role="MEMBER",
    email=claims["email"],
)
ok(
    "Editorially downgraded role still cannot escalate",
    decode_access_token(escalated).get("role") == "MEMBER"
    and not policy_engine.has_permission(decode_access_token(escalated), Permission.AUDIT_READ),
)

# =============================================================================
section("TEST 5: /auth/policy Exposes In-Memory Resolved Policy")
# =============================================================================
print("\n[TEST 5] Effective policy endpoint resolves with no permission lookups")

r = client.get(
    f"{base_url}/auth/policy", headers={"Authorization": f"Bearer {admin_token}"}
)
ok("GET /auth/policy returns 200", r.status_code == 200, r.text[:120] if r.status_code != 200 else "")
policy_body = r.json()
ok(
    "Admin policy matches the in-memory matrix",
    policy_body["role"] == "ADMIN"
    and sorted(policy_body["permissions"]) == sorted(ADMIN_PERMISSIONS),
    f"({len(policy_body.get('permissions', []))} permissions)",
)
ok(
    "Tenant boundary declared as enforced",
    policy_body["tenant_boundary_enforced"] is True
    and policy_body["rbac_mode"] == "stateless-in-memory-policy-matrix",
)

# =============================================================================
section("TEST 6: RBAC Enforcement Through The In-Memory Engine")
# =============================================================================
print("\n[TEST 6] Endpoint guards resolve from signed claims, not DB permission lookups")

r = client.post(
    f"{base_url}/departments/",
    headers={"Authorization": f"Bearer {member_body['access_token']}"},
    json={"name": "Unauthorized O-01 Attempt"},
)
ok("MEMBER blocked from department creation (403)", r.status_code == 403, f"-> {r.json().get('detail')}")

r = client.get(
    f"{base_url}/audit/logs", headers={"Authorization": f"Bearer {member_body['access_token']}"}
)
ok("MEMBER blocked from audit ledger (403)", r.status_code == 403, f"-> {r.json().get('detail')}")

r = client.get(
    f"{base_url}/audit/logs", headers={"Authorization": f"Bearer {admin_token}"}
)
ok("ADMIN permitted on audit ledger (200)", r.status_code == 200, f"-> {r.status_code}")

# =============================================================================
section("TEST 7: Single-Query Hybrid Offboarding Guard")
# =============================================================================
print("\n[TEST 7] Exactly one DB query per request verifies BOTH active flags")

from app.core.database import engine
from sqlalchemy import event

statements: list[str] = []
listener_registered = False


@event.listens_for(engine, "before_cursor_execute")
def _count_queries(conn, cursor, statement, parameters, context, executemany):
    if statement.lstrip().upper().startswith("SELECT"):
        statements.append(" ".join(statement.split()))


if not listener_registered:
    event.listen(engine, "before_cursor_execute", _count_queries)

statements.clear()
r = client.get(f"{base_url}/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
guard_queries = [s for s in statements if "FROM users" in s]
ok("GET /auth/me returns 200", r.status_code == 200, f"-> {r.status_code}")
ok(
    "Exactly one authorization SELECT executed",
    len(guard_queries) == 1,
    f"({len(guard_queries)} query)",
)
ok(
    "Guard query joins users -> tenants and reads both active flags",
    "join tenants" in guard_queries[0].lower()
    and "is_active" in guard_queries[0]
    and guard_queries[0].lower().count("is_active") >= 2,
    f"\n         SQL: {guard_queries[0][:150]}...",
)
event.remove(engine, "before_cursor_execute", _count_queries)

# =============================================================================
section("TEST 8: Instant Revocation - Offboarded Professional")
# =============================================================================
print("\n[TEST 8] Setting User.is_active=False revokes access on the next request")

offboard_email = "o01.offboard@azm-nexus.com"
offboard_token = None
db = SessionLocal()
try:
    existing = db.query(User).filter(User.email == offboard_email).first()
    if existing:
        existing.is_active = False
        db.commit()
        existing.is_active = True
        db.commit()
        offboard_id = existing.id
    else:
        from app.core.security import get_password_hash

        offboard_id = uuid.uuid4()
        db.add(
            User(
                id=offboard_id,
                tenant_id=uuid.UUID(admin_body["tenant_id"]),
                email=offboard_email,
                hashed_password=get_password_hash("Offboard123!"),
                role=UserRole.MEMBER,
                is_active=True,
            )
        )
        db.commit()
    ok("Offboarding fixture provisioned", True, f"({offboard_email})")

    # Token is minted while active - it is cryptographically valid and unexpired.
    offboard_token = create_access_token(
        subject=str(offboard_id),
        tenant_id=str(admin_body["tenant_id"]),
        role="ADMIN",
        email=offboard_email,
    )
    r = client.get(
        f"{base_url}/auth/me", headers={"Authorization": f"Bearer {offboard_token}"}
    )
    ok("Token works while the account is active", r.status_code == 200, f"-> {r.status_code}")

    # Offboard the professional: only the guard query changes the outcome.
    victim = db.query(User).filter(User.id == offboard_id).first()
    victim.is_active = False
    db.commit()

    r = client.get(
        f"{base_url}/auth/me", headers={"Authorization": f"Bearer {offboard_token}"}
    )
    ok(
        "Offboarded user rejected with 403 on the very next request",
        r.status_code == 403,
        f"-> {r.status_code} {r.json().get('detail')}",
    )
    r = client.get(
        f"{base_url}/audit/logs", headers={"Authorization": f"Bearer {offboard_token}"}
    )
    ok(
        "Offboarded user's otherwise-valid ADMIN token is powerless",
        r.status_code == 403,
        f"-> {r.status_code}",
    )
    r = login(offboard_email, "Offboard123!")
    ok("Offboarded user cannot re-authenticate", r.status_code == 403, f"-> {r.status_code}")

    victim.is_active = True
    db.commit()
finally:
    db.close()

# =============================================================================
section("TEST 9: Instant Revocation - Suspended Tenant")
# =============================================================================
print("\n[TEST 9] Setting Tenant.is_active=False revokes the entire workspace")

db = SessionLocal()
try:
    tenant = db.query(Tenant).filter(Tenant.id == uuid.UUID(admin_body["tenant_id"])).first()
    ok("Tenant located", tenant is not None, f"(slug={tenant.slug}, active={tenant.is_active})")

    tenant.is_active = False
    db.commit()

    r = client.get(
        f"{base_url}/auth/me", headers={"Authorization": f"Bearer {admin_token}"}
    )
    ok(
        "Suspended tenant blocks an otherwise-valid ADMIN token (403)",
        r.status_code == 403,
        f"-> {r.status_code} {r.json().get('detail')}",
    )
    r = login(*ADMIN)
    ok("Suspended tenant refuses new logins", r.status_code == 403, f"-> {r.status_code}")

    tenant.is_active = True
    db.commit()

    r = client.get(
        f"{base_url}/auth/me", headers={"Authorization": f"Bearer {admin_token}"}
    )
    ok(
        "Reactivation restores access immediately",
        r.status_code == 200,
        f"-> {r.status_code}",
    )
finally:
    db.close()

# =============================================================================
section("TEST 10: Repository Guard Contract")
# =============================================================================
print("\n[TEST 10] UserRepository.get_lifecycle_flags contract")

db = SessionLocal()
try:
    repo = UserRepository(db)
    guard = repo.get_lifecycle_flags(uuid.UUID(admin_body["user_id"]))
    ok(
        "Guard returns the hydrated user plus the tenant flag",
        guard.user is not None and guard.tenant_is_active is True,
        f"(user={guard.user.email if guard.user else None}, tenant_active={guard.tenant_is_active})",
    )
    ghost = repo.get_lifecycle_flags(uuid.uuid4())
    ok(
        "Unknown principal yields a fail-closed guard",
        ghost.user is None and ghost.tenant_is_active is None,
    )
finally:
    db.close()

# =============================================================================
print(f"\n{'=' * 78}")
print(f"DWOP-017 / TASK O-01: ALL {PASSED} STATELESS RBAC ASSERTIONS PASSED")
print(f"{'=' * 78}")