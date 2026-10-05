# Gate 2 Security Review Package — Task O-02

**Document Version**: 1.0
**Date**: 2026-10-05
**Status**: Submitted for formal security review
**Reviewer**: Khalifa
**Requester**: AZM Nexus Core Backend Engineering
**Task**: O-02 — RBAC Permission Matrix Publication & Team Lead Derived Scope
**ADR**: [`docs/adr-002-stateless-rbac-scaling.md`](adr-002-stateless-rbac-scaling.md) (§6.1)
**Commit**: `37bdb42` on `feature/o01-stateless-rbac`

---

## 1. Scope of Review

This package covers the authorization model changes delivered by Task O-02. It
does **not** re-review the O-01 baseline (stateless `PolicyEngine`, signed JWT
claims, hybrid offboarding guard), which was reviewed under O-01 and is unchanged
in its mechanics — only its permission identifiers and its scope-evaluation path
were extended.

| In scope | Out of scope |
|---|---|
| `docs/rbac-matrix.md` — the published permission matrix | Authentication, password hashing, refresh-token rotation |
| `backend/app/core/policy.py` — `POLICY_MATRIX`, `SCOPE_MATRIX`, `RESOURCE_BOUND_SCOPES`, `LEGACY_PERMISSION_ALIASES`, scope evaluation | Provider adapter integrations, audit-ledger immutability |
| `backend/app/core/scopes.py` — `ScopeResolver`, `ScopeGrant` | Frontend RBAC-aware navigation |
| `backend/app/core/dependencies.py` — `enforce_scope_boundary` | Horizontal scaling / replica topology |
| `backend/app/core/security.py` — `scopes` / `lead_teams` claim issuance | O-05 fifteen-minute-token path |
| `backend/app/api/auth.py` — login, refresh, `GET /auth/policy` | |

---

## 2. Artifacts Under Review

| Artifact | Purpose |
|---|---|
| [`docs/rbac-matrix.md`](rbac-matrix.md) | Single authoritative, audit-ready permission matrix |
| [`backend/app/core/policy.py`](../backend/app/core/policy.py) | Permission catalogue, frozen matrices, `PolicyEngine` |
| [`backend/app/core/scopes.py`](../backend/app/core/scopes.py) | Derived-scope resolution from `Team.team_lead_id` |
| [`backend/app/core/dependencies.py`](../backend/app/core/dependencies.py) | RBAC dependency factories, `enforce_scope_boundary` |
| [`backend/app/core/security.py`](../backend/app/core/security.py) | Signed claim issuance and verification |
| [`backend/app/api/auth.py`](../backend/app/api/auth.py) | Token issuance, refresh, effective-policy endpoint |
| [`backend/scripts/test_dwop018_rbac_matrix.py`](../backend/scripts/test_dwop018_rbac_matrix.py) | Suite 14 — matrix sync and derived-scope verification (57 assertions) |
| [`backend/scripts/test_dwop017_stateless_rbac.py`](../backend/scripts/test_dwop017_stateless_rbac.py) | Suite 13 — engine and offboarding guard (41 assertions) |

---

## 3. Decisions Requiring Sign-Off

Each decision below is stated with its rationale and the evidence that supports
it. Reviewer comment is requested against each numbered item.

### D1 — Team Lead is a derived scope, not a fourth role

**Decision.** Team-lead authority is derived at token issuance from
`Team.team_lead_id` and emitted as signed `scopes` + `lead_teams` claims. It is
not a `UserRole` member and is never persisted in `users.role`.

**Rationale.** A fourth role would require a schema migration, a new enum value,
and would make team-lead authority tenant-wide rather than team-scoped. Deriving
it keeps the authority resource-bound and reversible in a single write.

**Evidence.** `test_dwop018_rbac_matrix.py` asserts `UserRole` has exactly three
members, that derivation never mutates `users.role`, and that clearing
`team_lead_id` removes the scope on the next issuance.

**Reviewer question.** Is a derived scope an acceptable substitute for a stored
role for audit purposes, given that the derivation source (`Team.team_lead_id`)
is itself an auditable, Administrator-only write?

### D2 — Scope authority is strictly narrower than Manager authority

**Decision.** Evaluation order is tenant boundary → role breadth → scope breadth.
A `team_lead` grant is honoured only when the target resource's team appears in
the signed `lead_teams` binding.

**Rationale.** Prevents a team lead from acquiring tenant-wide reach through a
scope that overlaps Manager authority, and guarantees the tenant boundary is
evaluated before any scope logic.

**Evidence.** Tested for own-team allow, foreign-team deny, cross-tenant deny,
and no-team fail-closed.

**Reviewer question.** Is the ordering tenant → role → scope correct for all
resource types, or are there resources where scope must be evaluated first?

### D3 — No client-controlled value participates in authorization

**Decision.** `enforce_scope_boundary` requires the team identifier the endpoint
loaded from the database. A client-supplied `team_id` query parameter was
evaluated during design and rejected.

**Rationale.** Accepting a request-controlled team identifier would let any
authenticated caller assert arbitrary scope by varying a query string.

**Evidence.** The dependency signature takes `resource_team_id` from the
endpoint's own repository lookup; no `Query(...)` parameter exists in the
authorization path.

**Reviewer question.** Confirm no endpoint passes a client-supplied identifier
into `enforce_scope_boundary`.

### D4 — Bounded staleness for role and scope changes

**Decision.** Because resolution is stateless, a revoked role or derived scope
propagates on the caller's next token issuance, bounded by the access-token
lifetime.

**Rationale.** This is the O-01 trade-off retained deliberately: it is what keeps
authorization free of per-request permission lookups. It is asserted by test
rather than left implicit.

**Evidence.** `test_dwop018_rbac_matrix.py` asserts that a stale token retains
its signed scope authority until expiry, and that it cannot exceed the
`lead_teams` binding it was signed with.

**Reviewer question.** Is the access-token lifetime an acceptable maximum
staleness window for team-lead revocation, or must scope revocation be
instantaneous (which would require a per-request lookup)?

### D5 — Legacy alias table is read-side only

**Decision.** `LEGACY_PERMISSION_ALIASES` (33 entries) resolves O-01 identifiers
so in-flight tokens survive a rolling deploy. Newly issued tokens carry
canonical O-02 strings only.

**Rationale.** Avoids a hard cutover. The alias table is never consulted for
issuance, so it cannot widen authority.

**Evidence.** Tested that alias resolution maps to canonical identifiers and is
a no-op for canonical input.

**Reviewer question.** Confirm the alias table should be removed in a later
task once O-01 tokens have expired, rather than being retained indefinitely.

### D6 — Documentation is a build gate

**Decision.** `docs/rbac-matrix.md` is the single source of truth for the
matrix. Suite 14 parses every capability table and fails the build on divergence
in either direction.

**Rationale.** Prevents the document from becoming descriptive drift.

**Evidence.** The gate caught two real defects during development: an
identifier-format validator that rejected the legitimate `people:bulk_import`
underscore segment, and a miscounted Manager tier (24 published vs 23 actual).

**Reviewer question.** Acceptable that the document is enforced by test rather
than by a separate policy-as-code tool?

---

## 4. Security Properties — Summary

| Property | Mechanism | Verified |
|---|---|---|
| Tenant isolation | `tenant_id` claim compared to resource tenant, before role breadth | Suite 13 |
| Instant revocation | Single per-request query on `User.is_active` + `Tenant.is_active` | Suite 13 |
| Claim integrity | Signature, issuer, audience, expiry verification | Suite 13 |
| Scope containment | Signed `lead_teams` binding, resource-bound evaluation | Suite 14 |
| Fail closed | Missing role/tenant/scope/resource-team all deny | Suites 13, 14 |
| No privilege escalation via scope | Scope grants ⊂ Manager grants | Suite 14 |
| Segregation of duties | Bulk import, revocation, blueprint authoring, team-lead assignment are Administrator-only | Suite 14 |
| Auditability | Team-lead assignment is an Administrator-only write to `Team.team_lead_id` | Suite 14 |

---

## 5. Verification Evidence

| Check | Result |
|---|---|
| Suites 1–12 (pre-existing) | green |
| Suite 13 `test_dwop017_stateless_rbac.py` | 41/41 |
| Suite 14 `test_dwop018_rbac_matrix.py` | 57/57 |
| `test_default_github_integration_seed.py` | green |
| `alembic upgrade head → downgrade -1 → upgrade head` | verified on a clean database |
| Measured policy resolution | ~17 µs per evaluation (unchanged from O-01) |

**198 measured assertions** across the suites reporting `[PASS]` counters.

---

## 6. Reviewer Sign-Off

| # | Decision | Accepted | Comments |
|---|---|:--:|---|
| D1 | Team Lead as derived scope | ☐ | |
| D2 | Scope strictly narrower than Manager | ☐ | |
| D3 | No client-controlled authorization input | ☐ | |
| D4 | Bounded staleness for role/scope changes | ☐ | |
| D5 | Read-side legacy alias table | ☐ | |
| D6 | Documentation enforced as a build gate | ☐ | |

**Reviewer**: Khalifa
**Outcome**: ☐ Approved — Gate 2 cleared ☐ Approved with conditions ☐ Changes required
**Date**: ____________

---

## 7. Conditions for Gate 2 Clearance

1. All six decisions in §3 accepted, or accepted with documented conditions.
2. No condition may weaken tenant isolation, fail-closed behaviour, or the
   prohibition on client-controlled authorization input.
3. Any condition affecting the staleness window (D4) must state the compensating
   control, since it is the one property that trades revocation speed for
   statelessness.