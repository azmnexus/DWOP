# ADR-002: Stateless RBAC Policy Engine for Horizontal Scaling

**Status**: Accepted (Gate 2, pending Khalifa security sign-off)
**Date**: 2026-10-05 (Updated 2026-10-08 per CTO Directive)
**Authors**: AZM Nexus Core Backend Engineering (Tasks O-01, O-02)
**Deciders**: AZM Nexus Engineering Leadership (CTO: Mr. Sadiq)
**Published matrix**: [`docs/rbac-matrix.md`](rbac-matrix.md) — the single authoritative, audit-ready permission matrix. Every permission string used by this ADR is defined there.
**Supersedes/Refines**: ADR-001 Trigger 3 (Horizontal API replicas) and ADR-001 `Caching: None — Every request hits DB`

---

## 1. Context

DWOP Sprint 0 authenticates with stateless JWTs and enforces RBAC with four hardcoded FastAPI dependencies (`get_current_active_user`, `require_admin`, `require_admin_or_manager`). Three structural problems block the ADR-001 scaling path to 1,000 concurrent active users:

1. **Authorization logic is scattered and duplicated.** Role knowledge lives in dependency functions, in service-layer `if role == UserRole.MEMBER` branches (`AccessService`, `OnboardingService`), and as string-literal comparisons inside state-machine transition guards (`TicketStateMachine`). A role change requires edits across all three layers.
2. **The `role` claim is decorative.** `create_access_token` signs a `role` claim, but `get_current_user` never reads it — it re-reads the full `User` row on every request and every service re-reads `current_user.role`. The signed claim and the authorization decision are disconnected.
3. **No revocation path.** There is no denylist and no lifecycle flag on `Tenant`. An offboarded professional or a suspended workspace keeps working until their 60-minute token expires. `POST /auth/logout` is an audit event only — it invalidates nothing, while its response body claims the session was invalidated.

ADR-001 already commits the platform to horizontal API replicas behind an ALB ("JWT is stateless"). That commitment only holds if RBAC becomes genuinely stateless. This ADR closes the gap.

---

## 2. Decision

> **We adopt an In-Memory Policy Matrix embedded in application memory that evaluates cryptographically signed JWT claims, delivering sub-millisecond policy resolution with zero infrastructure dependencies.**

Concretely:

- The access JWT is signed with `SECRET_KEY` and embeds `role`, `tenant_id` and a fully expanded `perms` claim, alongside `sub`, `email`, `iat`, `jti`, `exp`, `iss` and `aud`.
- `backend/app/core/policy.py` holds a frozen `PolicyMatrix` mapping each role (`ADMIN`, `MANAGER`, `MEMBER`) to an immutable `frozenset` of permission identifiers, and a `PolicyEngine` that evaluates those permissions against the verified claims. The engine performs **no SQL, no cache lookup and no network call**. Resolution is a dict lookup plus set membership tests.
- All RBAC decisions — including the resource-scoped self-service rules that previously lived as `if role == MEMBER` branches — route through `PolicyEngine`.
- Tenant boundary checks are retained in full and evaluated on every resource-scoped decision, *before* permission membership. A broader role never authorizes a cross-tenant read.

### 2.1 The Hybrid Offboarding Guard

Pure statelessness alone is not acceptable: DWOP handles workforce offboarding and commercial tenant suspension, both of which require **instant** revocation. So authorization is hybrid, not purely stateless:

| Concern | Resolver | Round-trips per request |
|---|---|---|
| Role / permission decision | `PolicyEngine` (signed claims) | 0 |
| Tenant boundary check | `PolicyEngine` (signed claims) | 0 |
| User revocation (`User.is_active`) | Hybrid offboarding guard | 1 (shared) |
| Tenant suspension (`Tenant.is_active`) | Hybrid offboarding guard | 1 (shared) |

Exactly **one** lightweight database query runs per authenticated request. It joins `users` → `tenants` and returns the hydrated principal plus both lifecycle flags in the same round-trip. It is the *only* database access on the authorization path, and it is reserved for revocation — never for permission computing.

Net effect: DB round-trips on the authorization path drop from **N** (one per permission-checking call site) to **1**, and the RBAC computation itself adds zero latency.

---

## 3. Alternatives Considered

### 3.1 Rejected: Distributed Redis Caching

*Cache the permission/role lookup in Redis so every API replica shares one authoritative policy store.*

**Rejected.** For Sprint 0 this trades a sub-microsecond dict lookup for a network round-trip that costs more than the entire authorization budget:

- **Unwarranted infrastructure overhead.** Redis is a stateful, in-memory datastore that must be provisioned, secured, TLS-terminated, monitored, given a failover story, and included in on-call runbooks. DWOP's authorization working set is three roles and ~37 permission strings — kilobytes, not gigabytes. Redis would be a distributed system introduced to store a constant.
- **External network latency hops.** Every authorization decision would require a round-trip to another host (~0.3–1 ms RTT on a same-region network, plus serialization). ADR-002's measured in-memory resolution is ~17 µs. The cache would be **20–50× slower than the thing it replaces**, and would put the authorization path's availability hostage to a dependency DWOP does not otherwise need.
- **Cache-invalidation race conditions during membership changes.** This is the disqualifying risk. Offboarding, team reassignment and tenant suspension are precisely the moments where a stale cached grant is most damaging. With a multi-replica deployment, invalidation becomes a distributed consensus problem: a `DEL` that races a concurrent `SET` can resurrect a revoked grant, and replicas observing the key at different moments disagree about whether the professional still holds access. Correctness would demand write-through invalidation, versioned keys, or pub/sub fan-out — each of which reintroduces the operational burden that motivated the cache, and each of which is strictly harder to reason about than a signed, immutable token claim.

The single-query offboarding guard already solves revocation against the authoritative database. A cache would add a second, weaker source of truth for the same question.

### 3.2 Rejected: Open Policy Agent (OPA) / External Policy Engines

*Delegate authorization to an Open Policy Agent deployment (or equivalent), with Rego policies evaluated by the engine.*

**Rejected.** OPA is the right answer for heterogeneous policy across many services and languages. DWOP is a single Python monolith with three roles:

- **Heavy daemon deployment complexity.** OPA is a separate control-plane service requiring its own binary distribution, bundle build pipeline, decision-log storage, and a discovery/registration mechanism. Decision logs add a second datastore. This is a platform-infrastructure project, not a Sprint 0 authorization change.
- **Sidecar overhead.** Per-pod sidecar deployment multiplies memory and CPU allocation by the pod count and introduces a local proxy hop on every authorization call. The sidecar must be versioned, patched and kept configuration-compatible with the application it fronts — a second release train for what is a static mapping table.
- **Operational maintenance burdens.** Rego policies are a second language with its own linter, test harness, review norms and failure modes (a policy bundle that fails to compile is an authorization outage). Engineers touching RBAC must now reason about two toolchains. Rego evaluation latency (~100 µs–1 ms) also exceeds the in-memory engine's cost, buying nothing.

The decision surface here is small, static and auditable in a code review. OPA earns its cost only when policy must be changed without a deployment, by a different team, across many runtimes.

### 3.3 Rejected: Additional Options

| Option | Why rejected |
|---|---|
| **DB-backed permission tables, queried per endpoint** | The status quo problem. Adds a join per authorization call, couples RBAC schema to product migrations, and cannot serve the ADR-001 horizontal path without a cache. |
| **JWT denylist (logout / revocation list)** | Requires a shared mutable store to be effective across replicas — Redis again. Adds a lookup to the hot path to solve a problem the one-query guard already solves from the authoritative database. |
| **Embed Casbin / `permify` as a library** | Genuinely stateless, but a large dependency and a persisted-policy-model file format for a 3-role matrix. The permission catalogue is a readable Python constant that a reviewer can audit in one screen. Reconsider at custom/ABAC role requirements. |
| **Pure statelessness, no revocation query** | Rejected on correctness: offboarding and tenant suspension would lag token expiry by up to 60 minutes. |
| **Rely on JWT `exp` alone for lifecycle** | Same as above, and leaves `Tenant` with no enforcement hook at all. |

---

## 4. Temporary 60-Minute Privilege-Downgrade Exposure

Per CTO Directive (Mr. Sadiq, Gate 2 Execution Order):

### 4.1 Vulnerability Window & Threat Profile
Under the stateless RBAC policy engine, access tokens carry signed role and permission claims. Because token verification evaluates these claims in memory with zero database or cache lookups:
- If an administrator downgrades a user's role (e.g., from `ADMIN` to `MEMBER`, or `MANAGER` to `MEMBER`), the user's currently active access token will **continue to assert the higher privilege level** until the token expires.
- Under the current milestone configuration, `ACCESS_TOKEN_EXPIRE_MINUTES = 60`, which defines a **maximum 60-minute privilege-downgrade exposure window**.

### 4.2 Mitigations in Place
1. **Immediate Offboarding Guards (`User.is_active` & `Tenant.is_active`)**:
   - The hybrid offboarding guard checks `User.is_active` and `Tenant.is_active` on every authenticated request via a single lightweight database round-trip.
   - If an account is deactivated or offboarded entirely, access is revoked **immediately on the very next request**, regardless of the 60-minute token lifetime.
   - Similarly, if an entire commercial tenant workspace is suspended, all sessions under that tenant are blocked instantly.
2. **Explicit CTO Decision on `token_version`**:
   - The CTO has explicitly mandated that the `token_version` mechanism is **NOT implemented for this milestone** to avoid introducing stateful DB lookups into the policy evaluation path and preserve architectural simplicity during Gate 2.

### 4.3 Target Remediation Milestone
The permanent remediation for the privilege-downgrade exposure window is scheduled for the upcoming **Token Lifecycle Milestone (O-05)**:
- **Shorten Access Token Lifetime to 15 Minutes**: `ACCESS_TOKEN_EXPIRE_MINUTES` will be reduced from 60 to 15 minutes, bounding any privilege-change window to at most 15 minutes.
- **HttpOnly Refresh Token Rotation Flow**: Introduce a secure, rotated refresh token flow. Role updates trigger immediate revocation of the refresh token family. On the next 15-minute token refresh cycle, the client is forced to re-authenticate or re-mint against updated database credentials, ensuring prompt policy propagation without burdening normal request processing with database overhead.

---

## 5. Consequences

### Positive

- **Sub-millisecond policy resolution** with **zero infrastructure dependencies**. No Redis, no OPA, no new datastore, no new failure mode, nothing to page on.
- **One DB round-trip per authenticated request** on the authorization path, down from N.
- **Single source of truth for RBAC.** `POLICY_MATRIX` replaces scattered `if role == ...` branches in dependencies, services and state-machine guards.
- **Horizontal scaling is now real.** Replicas share no authorization state; ADR-001 Trigger 3 ("JWT is stateless") is finally accurate.
- **Instant revocation** for both offboarded professionals and suspended tenants via the hybrid guard.
- **Tenant isolation hardened.** The `tenant_id` claim is load-bearing — a claim/row mismatch is a 401, and cross-tenant access is denied before permission membership is consulted.
- **Auditable permissions.** The `perms` claim and `GET /auth/policy` make each principal's effective authority directly inspectable.

### Negative / Trade-offs

- **Privilege-downgrade window (60 minutes).** Documented in §4 above. Mitigated by `User.is_active` and `Tenant.is_active` deactivation guards.
- **The matrix must be deployed, not configured.** Changing RBAC requires a release. Accepted: with three roles this is cheap, and it makes every policy change a code-reviewable artifact.
- **Claims are larger.** The ADMIN token embeds 37 permission strings, adding roughly 900 bytes to the header. Negligible versus the elimination of database queries.
- **Custom/ABAC roles are out of scope.** Per-resource attribute checks remain in the service layer, resolved through the engine. Revisit if ADR-003 requires ABAC.

---

## 6. Implementation Map

| Concern | Location |
|---|---|
| **Published permission matrix (authoritative)** | **`docs/rbac-matrix.md`** |
| Derived-scope resolver (`Team.team_lead_id` → signed claims) | `backend/app/core/scopes.py` (`ScopeResolver`, `ScopeGrant`) |
| Permission catalogue + frozen policy matrix + `POLICY_MATRIX` / `SCOPE_MATRIX` + `PolicyEngine` | `backend/app/core/policy.py` |
| Legacy read-side alias table for rolling deploys | `backend/app/core/policy.py` (`LEGACY_PERMISSION_ALIASES`, 33 entries) |
| Signed `role` / `tenant_id` / `perms` / `scopes` / `lead_teams` claim issuance and verification | `backend/app/core/security.py` |
| Token verification, hybrid offboarding guard, RBAC dependency factories, `enforce_scope_boundary` | `backend/app/core/dependencies.py` |
| Single-query guard (`users` ⨝ `tenants`, both `is_active` flags) | `backend/app/repositories/user.py` (`get_lifecycle_flags`) |
| Workspace lifecycle flag | `backend/app/models/tenant.py` (`Tenant.is_active`) |
| Schema migration | `backend/alembic/versions/0003_tenant_lifecycle_guard.py` |
| Effective-policy introspection endpoint (role vs. effective, scopes) | `backend/app/api/auth.py` (`GET /auth/policy`) |
| Service/resource rules routed through the engine | `backend/app/services/access.py`, `backend/app/services/onboarding.py`, `backend/app/core/state_machines.py` |
| Verification suite — regression suite sweep (all 14 suites) | `backend/scripts/` |

### 6.1 Team Lead as a Derived Scope (No Fourth Role)

Team Lead authority is *not* a `UserRole` member and is *not* persisted in `users.role`. It is derived at token issuance from `Team.team_lead_id` by `ScopeResolver` and emitted as the signed `scopes: ["team_lead"]` plus `lead_teams: [...]` claims. Consequence: **zero schema migrations** — `teams.team_lead_id` already exists.

The scope grants five resource-bound permissions (`people:read:all`, `people:intake`, `onboarding:runs:create`, `assignments:read:all`, `assignments:allocate`), each evaluated only when the target resource's team appears in the signed `lead_teams` binding. Evaluation order is tenant boundary, then role breadth, then scope breadth, so Team Lead authority is always strictly narrower than the Manager authority it overlaps.
