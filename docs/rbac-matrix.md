# DWOP RBAC Permission Matrix

**Document Version**: 1.0
**Status**: Approved for Gate 2 security review
**Date**: 2026-10-05
**Owners**: AZM Nexus Engineering Leadership (Security Review: Khalifa)
**Authoritative Source**: This document
**Enforcement Code**: `backend/app/core/policy.py` (`POLICY_MATRIX`, `SCOPE_MATRIX`)
**Governing ADR**: [`docs/adr-002-stateless-rbac-scaling.md`](adr-002-stateless-rbac-scaling.md)
**Task**: O-02 — Publication of the RBAC Permission Matrix

---

## 1. Purpose and Authority

This document is the **single authoritative, audit-ready permission matrix** for the
DWOP platform. It governs all system operations. Every permission string listed
here is:

1. Present in the in-memory `POLICY_MATRIX` / `SCOPE_MATRIX` configuration tables, and
2. Verified to be in exact bidirectional sync by
   `backend/scripts/test_dwop018_rbac_matrix.py`, which fails the build if this
   document and the code ever disagree.

If a permission exists in the code but not in this document (or the reverse), the
build fails. This document is therefore a **machine-verified control artifact**, not
a descriptive document.

### 1.1 Normalization Rules

- **Operational identifier format.** Every permission is `<domain>:<action>` or
  `<domain>:<action>:<qualifier>`. Domains are the plural operational nouns the
  platform acts on (`people`, `assignments`, `access`, `audit`, …).
- **The `:all` qualifier grants tenant-wide reach.** Its absence scopes the action
  to the caller's own records. This is the self-service boundary and is enforced in
  the service layer against the resolved resource.
- **Authority composition is additive.** `MANAGER` inherits every `MEMBER`
  permission. `ADMIN` inherits every `MANAGER` permission. Sets are strictly nested,
  which is asserted by test.
- **No wildcard is granted.** The engine recognises `*` as a superuser sentinel for
  future custom roles, but no locked tier and no derived scope holds it.

---

## 2. Locked Enterprise Access Tiers

Three tiers are locked. They map 1:1 onto `users.role` (`UserRole`).

| Tier | Stored value | Scope of authority | Persisted? |
|---|---|---|---|
| **Administrator** | `ADMIN` | Entire tenant + governance | Yes, `users.role` |
| **Manager** | `MANAGER` | Entire tenant, delegated domains only | Yes, `users.role` |
| **Member** | `MEMBER` | Own records only | Yes, `users.role` |

**Team Lead is deliberately absent from this table.** It is not a tier. See §5.

---

## 3. Functional Capability Definitions

| Capability | Operational domain | Description |
|---|---|---|
| Workspace administration | `tenant` | Read and administer the tenant workspace record, plan tier and branding. |
| Organisation structure | `departments`, `teams`, `clients`, `projects` | Read and administer the organisational tree and commercial entities. |
| Workforce management | `people` | Read, intake, bulk import and update professional records. |
| Onboarding governance | `onboarding` | Author onboarding blueprints, instantiate runs, and progress checklist items. |
| Capacity allocation | `assignments` | Read and allocate professional capacity against projects, bounded by the 100% hard ceiling. |
| Access lifecycle | `access`, `integrations` | Request, approve, provision and revoke third-party tool access; manage provider integrations. |
| Audit and governance | `audit` | Read and export the immutable audit ledger. |
| Identity administration | `users` | Administer user identities and role assignment. |

---

## 4. The Matrix

`✔` = granted. `—` = not granted. Blank cells are inherited, shown explicitly for
audit completeness.

### 4.1 Workspace — `tenant`

| Permission | Definition | Member | Manager | Admin |
|---|---|:--:|:--:|:--:|
| `tenant:read` | View the tenant workspace record and branding | ✔ | ✔ | ✔ |
| `tenant:update` | Modify tenant name, domain, plan tier, branding | — | — | ✔ |

### 4.2 Organisation structure — `departments`, `teams`, `clients`, `projects`

| Permission | Definition | Member | Manager | Admin |
|---|---|:--:|:--:|:--:|
| `departments:read` | List and view departments | ✔ | ✔ | ✔ |
| `departments:manage` | Create, rename, re-parent and delete departments | — | — | ✔ |
| `teams:read` | List and view teams | ✔ | ✔ | ✔ |
| `teams:manage` | Create, rename and delete teams; assign team leads | — | — | ✔ |
| `clients:read` | List and view client accounts | ✔ | ✔ | ✔ |
| `clients:manage` | Create and update client accounts | — | — | ✔ |
| `projects:read` | List and view projects | ✔ | ✔ | ✔ |
| `projects:manage` | Create and update projects | — | — | ✔ |

> **Audit note.** `teams:manage` is Administrator-only. Assigning or removing a
> `team_lead_id` is therefore a privileged, auditable act. A Member or Manager can
> never grant themselves Team Lead authority.

### 4.3 Workforce — `people`

| Permission | Definition | Member | Manager | Admin |
|---|---|:--:|:--:|:--:|
| `people:read` | Read own professional profile | ✔ | ✔ | ✔ |
| `people:read:all` | Read every professional record in the tenant | — | ✔ | ✔ |
| `people:intake` | Register a new professional (single intake) | — | ✔ | ✔ |
| `people:bulk_import` | Register a professional cohort atomically | — | — | ✔ |
| `people:update` | Amend an existing professional record | — | — | ✔ |

> **Audit note.** `people:bulk_import` is deliberately Administrator-only: it is a
> high-volume write path, so it is excluded from Manager authority even though
> `people:intake` is granted.

### 4.4 Onboarding — `onboarding`

| Permission | Definition | Member | Manager | Admin |
|---|---|:--:|:--:|:--:|
| `onboarding:templates:read` | View onboarding blueprints | ✔ | ✔ | ✔ |
| `onboarding:templates:manage` | Author and version onboarding blueprints | — | — | ✔ |
| `onboarding:runs:read` | Read own onboarding run | ✔ | ✔ | ✔ |
| `onboarding:runs:read:all` | Read every onboarding run in the tenant | — | ✔ | ✔ |
| `onboarding:runs:create` | Instantiate an onboarding run for a professional | — | ✔ | ✔ |
| `onboarding:items:complete` | Progress checklist items on own onboarding run | ✔ | ✔ | ✔ |
| `onboarding:items:manage` | Progress any checklist item, any run | — | — | ✔ |

> **Audit note.** `onboarding:items:complete` is bound at the service layer to the
> professional who owns the run. Holding the permission without owning the resource
> is a 403, not a silent success.

### 4.5 Capacity allocation — `assignments`

| Permission | Definition | Member | Manager | Admin |
|---|---|:--:|:--:|:--:|
| `assignments:read` | Read own allocations | ✔ | ✔ | ✔ |
| `assignments:read:all` | Read all allocations in the tenant | — | ✔ | ✔ |
| `assignments:allocate` | Allocate capacity to a project (100% hard ceiling enforced) | — | ✔ | ✔ |
| `assignments:update` | Adjust capacity, complete or reassign an allocation | — | ✔ | ✔ |

### 4.6 Access request lifecycle — `access`, `integrations`

| Permission | Definition | Member | Manager | Admin |
|---|---|:--:|:--:|:--:|
| `access:read` | Read own access requests | ✔ | ✔ | ✔ |
| `access:read:all` | Read every access request in the tenant | — | ✔ | ✔ |
| `access:request` | Submit an access request for own professional profile | ✔ | ✔ | ✔ |
| `access:request:any` | Submit an access request for any professional | — | ✔ | ✔ |
| `access:approve` | Approve a pending access request | — | ✔ | ✔ |
| `access:provision` | Execute provider provisioning for an approved request | — | ✔ | ✔ |
| `access:revoke` | Revoke provisioned third-party access | — | — | ✔ |
| `integrations:manage` | Register and configure provider integrations | — | — | ✔ |

> **Audit note.** `access:approve` for a Manager is additionally constrained by the
> **direct-report rule**: a Manager may only approve requests for professionals they
> supervise, verified through an active onboarding assignment. This is a
> resource-scoped rule layered on top of the permission and is evaluated in
> `AccessService`. Administrator approval is not direct-report constrained.
>
> `access:revoke` is Administrator-only: revocation is the highest-consequence
> access operation and is deliberately non-delegable.

### 4.7 Audit and governance — `audit`

| Permission | Definition | Member | Manager | Admin |
|---|---|:--:|:--:|:--:|
| `audit:read` | Read the immutable audit ledger and activity timeline | — | — | ✔ |
| `audit:export` | Export the tenant compliance ledger | — | — | ✔ |

> **Audit note.** The audit ledger is read-only for every tier. No role can mutate
> or delete an audit event; the repository enforces this with an immutability guard
> that raises rather than writing.

### 4.8 Identity administration — `users`

| Permission | Definition | Member | Manager | Admin |
|---|---|:--:|:--:|:--:|
| `users:manage` | Create users, change roles, activate/deactivate identities | — | — | ✔ |

---

## 5. Derived Scopes — Team Lead Authority

### 5.1 Definition

**Team Lead is a derived scope, not a role.** It confers authority that exists only
because a row points at the user:

```
Team.team_lead_id == user.id   →   user holds the `team_lead` derived scope
```

There is **no fourth global role**. Specifically:

| Constraint | How it is enforced |
|---|---|
| Not a `UserRole` member | `Team Lead` is absent from `UserRole` (`ADMIN`, `MANAGER`, `MEMBER` only). |
| Not persisted in `users.role` | Nothing writes `users.role` to express it. `users.role` is unchanged by any team-lead operation. |
| Not self-assignable | Derived at token issuance from `Team.team_lead_id`; there is no request path that grants it. |
| Not a schema change | **Zero migrations.** `teams.team_lead_id` already exists (ERD Entity: Team). |
| Reversible in one write | Clearing `team_lead_id` (including the existing `ON DELETE SET NULL` behaviour) removes the authority. |

### 5.2 Derivation

| Step | Behaviour |
|---|---|
| Source of truth | `Team.team_lead_id` |
| Derivation point | Token issuance (`POST /auth/login`) and re-issuance (`POST /auth/refresh`), via `ScopeResolver` in `backend/app/core/scopes.py` |
| Tenant scoping | Derivation is **tenant-relative**: only teams whose `Team.tenant_id` matches the caller's workspace can enter the `lead_teams` binding. A team the user leads in another tenant is invisible to the claim, so a signed token never carries an identifier from outside the caller's workspace. |
| Emission | Signed `scopes: ["team_lead"]` and `lead_teams: ["<team-uuid>", …]` JWT claims, emitted in stable sorted order so the claim is byte-identical across issuances for the same derivation |
| Evaluation | In-memory only, in `PolicyEngine.authorize` — no database access |
| Propagation | On the holder's next token issuance; ≤ 1 access-token lifetime otherwise |

### 5.3 Team Lead permissions (resource-bound)

| Permission | Definition | Member + `team_lead` | Manager | Admin |
|---|---|:--:|:--:|:--:|
| `people:read:all` | Read professionals **on their own teams** | ✔ (scoped) | ✔ (tenant) | ✔ (tenant) |
| `people:intake` | Register a professional **onto their own teams** | ✔ (scoped) | ✔ (tenant) | ✔ (tenant) |
| `onboarding:runs:create` | Instantiate runs **for their own teams** | ✔ (scoped) | ✔ (tenant) | ✔ (tenant) |
| `assignments:read:all` | Read allocations **for their own teams** | ✔ (scoped) | ✔ (tenant) | ✔ (tenant) |
| `assignments:allocate` | Allocate capacity **for their own teams** | ✔ (scoped) | ✔ (tenant) | ✔ (tenant) |

### 5.4 Strict scope boundary

Team Lead authority is **always narrower** than the Manager authority it overlaps:

- A `team_lead` grant is evaluated **only** when the target resource's team appears
  in the holder's signed `lead_teams` claim.
- Derivation is **tenant-relative**, so the `lead_teams` binding can never contain a
  team from outside the caller's workspace.
- A team lead who does not lead team X is denied on team X even with a valid,
  unexpired token.
- The tenant boundary is evaluated **before** the scope boundary. A team lead can
  never reach across tenants.
- When no team identifier is supplied to an evaluation that would rely on scope
  authority, the engine **fails closed**.
- Endpoints pass the team identifier they loaded **from the database**, never a value
  taken from the request. No client-supplied header, query parameter or body field
  participates in an authorization decision.

---

## 6. Tenant-Wide Security Rules

These rules apply to every permission in this document, regardless of tier.

### 6.1 Tenant isolation (mandatory, non-negotiable)

Every resource-scoped evaluation compares the subject's `tenant_id` claim against the
resource's tenant and denies on mismatch. **Tenant checks are never delegated to role
breadth** — an Administrator token is rejected for a cross-tenant identifier.

The `tenant_id` claim is load-bearing: a mismatch between the claim and the
authoritative user row is rejected with `401`, so the claim cannot be decorative.

Tenant context is sourced from the authoritative user row, never from the
client-controllable `X-Tenant-ID` header.

### 6.2 Instant revocation

The single per-request offboarding guard verifies both `User.is_active` and
`Tenant.is_active` in one query. Offboarding a professional or suspending a tenant
revokes access on the **very next request**, independent of token expiry, regardless
of tier or derived scope.

### 6.3 Fail closed

| Condition | Outcome |
|---|---|
| Missing or blank `role` claim | Denied |
| Role absent from `POLICY_MATRIX` | Denied |
| Missing `tenant_id` claim | Denied |
| Resource tenant cannot be determined | Denied |
| Cross-tenant resource | Denied |
| Derived scope not asserted in claims | Denied |
| Scope asserted but resource outside `lead_teams` | Denied |
| Resource-bound scope with no team identifier supplied | Denied |

### 6.4 Claim integrity

The access token is signed with `SECRET_KEY` and verified for signature, issuer,
audience and expiry. Editing `role`, `perms`, `scopes` or `lead_teams` invalidates the
signature and the token is rejected. The `perms` claim is a signed convenience
artefact for clients and the audit ledger — it is **never** used to widen authority.
The local matrix plus the verified `role` claim are authoritative.

### 6.5 Segregation of duties

| Rule | Enforced by |
|---|---|
| Bulk workforce import is Administrator-only | `people:bulk_import` absent from Manager |
| Access revocation is Administrator-only, non-delegable | `access:revoke` absent from Manager |
| Audit ledger is read-only for all tiers | Repository immutability guard, not RBAC |
| Onboarding blueprint authoring is Administrator-only | `onboarding:templates:manage` absent from Manager |
| Team lead assignment is Administrator-only | `teams:manage` absent from Manager |
| Manager approvals are direct-report constrained | Resource rule in `AccessService` layered on `access:approve` |

---

## 7. Enforcement Summary

| Concern | Resolver | DB round-trips per request |
|---|---|---|
| Role permission decision | `PolicyEngine` from signed `role` claim | 0 |
| Derived scope decision | `PolicyEngine` from signed `scopes` / `lead_teams` | 0 |
| Tenant boundary | `PolicyEngine` from signed `tenant_id` claim | 0 |
| User revocation | Hybrid offboarding guard | 1 (shared) |
| Tenant suspension | Hybrid offboarding guard | 1 (shared) |
| Scope derivation | `ScopeResolver` at token issuance only | issuance only |

Measured policy resolution: **~17 µs** per evaluation. Zero infrastructure
dependencies — no Redis, no external policy engine.

---

## 8. Change Control

1. Any change to a permission string, a tier's grants, or a derived scope requires
   a coordinated edit to this document **and** `backend/app/core/policy.py`.
2. `test_dwop018_rbac_matrix.py` enforces bidirectional sync; a mismatch fails the
   build. There is no path where the code and this document diverge silently.
3. Changes require formal security review by Khalifa before Gate 2 clearance.
4. Tier composition must remain strictly nested (`MEMBER` ⊂ `MANAGER` ⊂ `ADMIN`),
   asserted by test.
5. Adding a new tier to `UserRole` is a schema and migration change and is out of
   scope for this document. Adding a new *derived scope* is not, provided it adds no
   database role.