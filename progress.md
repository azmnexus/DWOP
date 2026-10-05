# DWOP Platform — Sprint 0 Engineering & Architecture Progress Report

**Document Version**: 1.4 (Sprint 0 / Task O-02 RBAC Permission Matrix Publication — ADR-002 Amendment)  
**Organization**: AZM Nexus Limited  
**System**: Digital Workforce Operations Platform (DWOP)  
**Status**: Completed through Ticket DWOP-009 (including DWOP-010 through DWOP-013, and DWOP-007/008 frontend), Tasks P-01 through P-06, **Gate 2 (Task O-01 Stateless RBAC Policy Engine)** and **Task O-02 (RBAC Permission Matrix Publication + Team Lead Derived Scope)**  


---

## 1. Executive Summary & Sprint Mission

AZM Nexus is advancing its operating model into a premier technology services and engineering advisory firm. The **Digital Workforce Operations Platform (DWOP)** serves as the internal control and orchestration plane that unifies:
- Workforce intake and talent classification
- Role-based onboarding checklists and compliance evidence
- Department, team, and capacity allocations
- Third-party tool access provisioning (GitHub, Slack, Trello, Google Workspace) via the Provider Adapter Pattern
- Immutable audit trails for all approvals and state transitions

### Primary Demo Goal (Friday Acceptance Gate)
Demonstrate an end-to-end synthetic operational lifecycle without manual database manipulation:
1. Intake a cohort of professionals via atomic bulk import.
2. Apply a standardized onboarding template generating tasks with calculated deadlines.
3. Track real-time progress, surface at least one blocker (e.g. 2FA hardware token), and show who is **Ready**, **Blocked**, or **Unassigned**.
4. Enforce strict Multi-Tenancy from Day 1 and Role-Based Access Control (RBAC).

---

## 2. Technical Stack & Architecture Baseline

| Layer | Technology | Architectural Purpose |
|---|---|---|
| **Backend API** | FastAPI + Python 3.11+ | Asynchronous I/O, strict Pydantic typing, auto-generated OpenAPI 3.1 specs |
| **Database** | PostgreSQL (with SQLite local fallback) | Relational integrity, JSONB semi-structured storage, ACID transactions |
| **ORM / Migrations** | SQLAlchemy 2.0 + Alembic | Strict type annotations, declarative mappings, versioned migrations |
| **Security & Auth** | `python-jose` (JWT) + `bcrypt` | Stateless bearer token authentication, secure password hashing |
| **Authorization (RBAC)** | In-Memory Policy Matrix (`app/core/policy.py`) | Stateless, sub-millisecond permission resolution from signed JWT claims, zero infrastructure dependencies ([ADR-002](file:///c:/Users/k3238/Documents/GitHub/DWOP/docs/adr-002-stateless-rbac-scaling.md)) |
| **Authorization Matrix** | Published, build-verified matrix ([`docs/rbac-matrix.md`](file:///c:/Users/k3238/Documents/GitHub/DWOP/docs/rbac-matrix.md)) | Single authoritative audit-ready permission catalogue; locked to the engine by Suite 14 |
| **Derived scopes** | `ScopeResolver` over `Team.team_lead_id` (`app/core/scopes.py`) | Team-lead authority as resource-bound scope — no fourth role, no migration |
| **Multi-Tenancy** | Python `contextvars.ContextVar` | Request-isolated tenant scoping via `TenantContextMiddleware` |
| **Frontend UI** | Next.js 14 + React + TypeScript | App Router, Lucide icons, responsive enterprise administration portal |

---

## 3. Sprint 0 Completed Backlog (Tickets DWOP-001 through DWOP-006)

### ✅ DWOP-001: Project Scaffolding & Working Agreement
- Root repository initialized with standard folder boundaries (`docs/`, `backend/`, `frontend/`).
- Master [`README.md`](file:///c:/Users/walid/OneDrive/Documents/Work/dwop-platform/README.md) defining team roles (Atanda, Khalifa, Walid, Usman, Oladotun).
- Configuration templates: `backend/.env.example` and `frontend/.env.local.example`.

### ✅ DWOP-002: Architecture Blueprint & API Boundaries
- High-level architecture diagram authored in Mermaid ([`docs/architecture.md`](file:///c:/Users/walid/OneDrive/Documents/Work/dwop-platform/docs/architecture.md)).
- Core API boundaries defined across 8 routers in `backend/app/api/`.
- Provider Adapter Pattern established in [`backend/app/integrations/base.py`](file:///c:/Users/walid/OneDrive/Documents/Work/dwop-platform/backend/app/integrations/base.py).

### ✅ DWOP-003: Core Organizational Models & Multi-Tenancy
- Implemented core SQLAlchemy models in FK dependency order:
  - `Tenant` (with `branding` JSONB and custom domain support)
  - `User` (system identities with role enum)
  - `Department` (hierarchical business units with manager FK)
  - `Team` (operational squads with team lead FK)
  - `Client` (commercial client organizations)
  - `Project` (delivery engagements with code and date ranges)
- Enforced strict tenant isolation: Every query filters by `tenant_id`, and write operations derive `tenant_id` from context rather than client input.

### ✅ DWOP-004: Authentication Baseline & RBAC Enforcement
- Implemented real database-backed authentication via `POST /api/v1/auth/login`.
- JWT access tokens issued containing `user_id`, `tenant_id`, `role`, and `email`.
- RBAC dependencies implemented:
  - `get_current_active_user`: Validates JWT, sets tenant context, permits read operations (`GET`).
  - `require_admin`: Strictly guards mutating operations (`POST`, `PUT`, `DELETE`).
- **Security Audit Evidence Verified**: Standard members attempting write actions are immediately blocked with `HTTP 403 Forbidden` (`"Admin privileges required for this operation."`).
- All seed passwords securely encrypted using `bcrypt` (never stored in plain text).

### ✅ DWOP-005: People & Intake Engine (Bulk Import)
- Separated `User` (system login identity) from `Professional` (workforce subject) per Section 8 of the directive.
- Created `Professional` and `Engagement` models with status enums and JSONB skills array.
- Endpoints implemented:
  - `POST /api/v1/people`: Single candidate intake guarded by `require_admin_or_manager`.
  - `GET /api/v1/people`: Scoped talent directory.
  - `POST /api/v1/people/bulk-import`: Atomic batch intake of talent cohorts in a single database transaction guarded by `require_admin`.

### ✅ DWOP-006: Onboarding Engine, Templates & Run State Machine
- Created 4 workflow models:
  - `OnboardingTemplate`: Reusable role-specific blueprints (`role_target`, `title`, `version`).
  - `ChecklistTemplateItem`: Step definitions with order index, required evidence types, and default due day offsets.
  - `OnboardingRun`: Active onboarding journey for a professional with calculated progress percentage.
  - `OnboardingItem`: Concrete tasks with status transitions (`pending` → `blocked` → `completed`), `blocker_reason`, and `evidence_ref`.
- Endpoints implemented:
  - `POST /api/v1/onboarding/templates`: Template authoring (Admin only).
  - `POST /api/v1/onboarding/runs`: Instantiates a run for a professional, auto-populating items and calculating deadlines.
  - `PATCH /api/v1/onboarding/runs/{run_id}/items/{item_id}`: Allows completing or blocking items with audit justifications.
  - `GET /api/v1/onboarding/runs/{run_id}`: Full run inspection with dynamic completion percentage.

### ✅ DWOP-009: Assignments & Capacity Allocation Engine (Walid)
- **Model**: Implemented `Assignment` (Table 9 of locked ERD) with foreign keys to `tenants.id`, `professionals.id`, `projects.id`, `teams.id`, role, capacity percentage, dates, and `status` (`active`, `completed`, `reassigned`).
- **Capacity Threshold Validation**:
  - Strict 100% hard-stop ceiling: Any allocation or update causing a professional's aggregate active capacity to exceed 100% across concurrent projects fails closed with `HTTP 400 Bad Request`.
  - Dynamic availability synchronization: Updates `availability_status` on `Professional` (`available` at 0%, `partially_booked` between 1% and 99%, `fully_booked` at 100%).
  - Lifecycle state synchronization: Automatically advances status from `ready` to `assigned` when allocated, and back to `ready` when capacity drops to 0%.
- **Atomic In-Transaction Audit Emission**:
  - `assignment.allocated` emitted upon creation with project, professional, and capacity metadata.
  - `assignment.updated` emitted upon status transition or capacity adjustment.
- **Endpoints Implemented in `backend/app/api/assignments.py`**:
  - `POST /api/v1/assignments/allocate`: Capacity allocation guarded by `require_admin_or_manager`.
  - `GET /api/v1/assignments/capacity`: Tenant-wide capacity overview (headcount, utilization, active counts).
  - `GET /api/v1/assignments/capacity/professionals/{id}`: Detailed capacity breakdown per talent profile.
  - `GET /api/v1/assignments`: Filterable list (`project_id`, `professional_id`, `status`).
  - `GET /api/v1/assignments/my-allocations`: Self-service allocations for authenticated professional.
  - `GET /api/v1/assignments/{id}`: Single assignment details.
  - `PATCH /api/v1/assignments/{id}`: Capacity adjustment and status lifecycle transitions.

### ✅ DWOP-010: Access Request Lifecycle (Oladotun + Walid Review)
- Implemented models: `Integration` (Table 14), `AccessRequest` (Table 15), `ApprovalDecision` (Table 16).
- Endpoints implemented:
  - `GET /api/v1/access/requests`: Scoped access request directory (Members restricted to own requests).
  - `POST /api/v1/access/requests`: Submit request in `requested` state.
  - `POST /api/v1/access/requests/{id}/approve`: Approvals with rationale (Admin global, Manager restricted to direct reports).
  - `POST /api/v1/access/requests/{id}/provision`: Calls provider adapter, transitions to `provisioned` or `failed`.
  - `POST /api/v1/access/requests/{id}/revoke`: Revocation endpoint guarded strictly by `require_admin`.
  - `GET /api/v1/access/requests/{id}/status`: Single request status inspection.

### ✅ DWOP-011: Provider Adapter Framework (Oladotun + Atanda)
- Provider-agnostic abstraction in `backend/app/integrations/base.py` (`BaseProviderAdapter`).
- Factory and registry pattern in `backend/app/integrations/factory.py` (`get_provider_adapter`, `register_provider_adapter`).
- Swappable provider mechanism without touching core domain services.

### ✅ DWOP-012: Safe GitHub Mock Adapter POC (Oladotun)
- In-memory sandbox implementation (`GitHubMockAdapter`) with zero network I/O (`network_io = False`).
- Supports idempotent provisioning, revocation, simulated failure fallback (`simulate_failure: True`), and fail-closed error handling.

### ✅ DWOP-013: Centralized Audit Service & Activity Timeline API (Khalifa / Walid)
- Created dedicated model `AuditEvent` (Table 19) in `backend/app/models/audit.py`.
- Centralized domain service `AuditService` in `backend/app/services/audit.py` (`log_event`, `list_logs`, `count_logs`).
- Retroactively hooked immutable audit emission into:
  - DWOP-004 Auth: `POST /api/v1/auth/login` emits `auth.login_successful`.
  - DWOP-005 People: `POST /api/v1/people` emits `professional.created`; `POST /api/v1/people/bulk-import` emits `professional.bulk_imported`.
  - DWOP-006 Onboarding: `POST /api/v1/onboarding/runs` emits `onboarding_run.created`; `PATCH /api/v1/onboarding/runs/{run_id}/items/{item_id}` emits `onboarding_item.status_changed`.
  - DWOP-010 Access: State changes emit `access_request.created`, `access_request.status_changed`, `access_request.revocation_failed`.
- Implemented read endpoints in `backend/app/api/audit.py`:
  - `GET /api/v1/audit/logs`: Filterable timeline (`actor_user_id`, `action`, `target_type`, `skip`, `limit`) guarded by `require_admin`.
  - `GET /api/v1/audit/export`: Tenant compliance ledger export summary.

### ✅ DWOP-007: Diamond Glass UI System, Auth Flow & Enterprise App Shell (Usman)
- **Design System & Aesthetics**:
  - Implemented the Diamond Glass visual design system using curated CSS custom properties in `frontend/src/app/globals.css`.
  - Glassmorphic translucent cards (`backdrop-filter: blur(12px)`), sapphire glowing borders, micro-interactions, responsive CSS grid.
  - Component library built in `frontend/src/components/ui/`: `Button`, `Input`, `Card`, `Badge`, `Skeleton`, `Toast`, `EmptyState`, `ErrorState`.
- **Authentication & State Management**:
  - `frontend/src/contexts/AuthContext.tsx`: Token persistence via `localStorage` and `js-cookie`, handling login, logout, and user session hydration.
  - `frontend/src/middleware.ts`: Next.js edge route protection redirecting unauthenticated users to `/login`.
  - `frontend/src/app/login/page.tsx`: Glassmorphic split-screen corporate login with animated gradient background, error banners, and demo credential quick-fill.
- **App Shell & Layout**:
  - `AppHeader`: Sticky diamond-blur header with tenant branding, search shortcut, notifications bell, and user avatar dropdown.
  - `Sidebar`: Desktop collapsible navigation with icon-accented active states and RBAC badge badges.
  - `MobileDrawer`: Slide-over responsive navigation drawer for mobile and tablet viewports.

### ✅ DWOP-008: Workforce Directory & Professional Profile View (Usman)
- **Workforce Directory (`/workforce`)**:
  - Real-time client-side search by name, email, or skill.
  - Status filters (`All`, `Intake`, `Onboarding`, `Ready`, `Active`, `Offboarding`, `Exited`).
  - Responsive data grid displaying avatar badges, contact details, skill chips, availability status, and dynamic action buttons.
  - Zero mock data: Fetches directly from `GET /api/v1/people` with Bearer auth headers.
  - Comprehensive states: Shimmer skeleton loaders during network transit, empty filter state, and inline retryable error states.
- **Professional Detail View (`/workforce/[id]`)**:
  - Deep-dive talent profile fetching from `GET /api/v1/people/{id}`.
  - Multi-card modular layout: Identity & Contact, Lifecycle & Availability, Skills & Expertise, and Contract Engagement Terms.
  - Supplementary onboarding runs check integration: Wired to `GET /api/v1/onboarding/runs?professional_id={id}`.

### ✅ Task P-01: Service Layer Pattern Extraction (Walid)
- **Extraction of `PeopleService` (`backend/app/services/people.py`)**:
  - Encapsulates talent listing, single intake/registration, profile query, profile update, and atomic batch intake with in-transaction audit emissions (`professional.created`, `professional.bulk_imported`).
  - Strict tenant scoping moved into the service layer for all queries and mutations.
  - Thinned `backend/app/api/people.py` into a declarative router delegating all domain logic to `PeopleService(db)`.
- **Extraction of `OnboardingService` (`backend/app/services/onboarding.py`)**:
  - Encapsulates onboarding template creation and listing, run instantiation with dynamic task generation and deadline calculations, run inspection with progress recalculation, and checklist item updates.
  - Preserves blocker-reason validation (`detail="Blocker reason is required when marking an item as blocked."`) and automatic run progress recalculation.
  - In-transaction audit emissions (`onboarding_run.created`, `onboarding_item.status_changed`) preserved within the active DB transaction.
  - Thinned `backend/app/api/onboarding.py` into a declarative router delegating to `OnboardingService(db)`.
- **Extraction of `OrganizationService` (`backend/app/services/organization.py`)**:
  - Encapsulates multi-tenant department and team operations (CRUD, listings scoped by tenant and department).
  - Implements circular dependency hierarchy prevention (`_validate_hierarchy`) that traverses the ancestor tree to prevent self-parenting and cyclic department hierarchies.
  - Thinned `backend/app/api/departments.py` and `backend/app/api/teams.py` into declarative routers delegating to `OrganizationService(db)`.
- **Packaging & Boundary Integrity**:
  - Updated `backend/app/services/__init__.py` exporting `AuditService`, `AccessService`, `AssignmentService`, `PeopleService`, `OnboardingService`, and `OrganizationService`.
### ✅ Task P-04: Adapter Pattern Formalization (Walid)
- **Typed Result Contract (`backend/app/integrations/result.py`)**:
  - Implemented immutable `AdapterResult` as `@dataclass(frozen=True)` aligned with the Directive specification: primary fields `external_id: str | None` and `error_message: str | None`, along with `success: bool`, `status: str`, `provider: str`, and `metadata: Dict[str, Any]`.
  - Added backward-compatible aliases (`external_reference`, `error`) and transitional mapping shims (`__bool__`, `__getitem__`, `get`, `to_dict`) marked `DEPRECATED` in docstrings, preserving legacy dictionary access while guiding callers toward typed attribute consumption.
- **Abstract Interface Standard (`backend/app/integrations/base.py`)**:
  - Formalized `BaseProviderAdapter` enforcing `@abstractmethod` returning `AdapterResult` on `provision_access`, `revoke_access`, and `get_status`.
  - Aligned signatures with the Directive specification: `provision_access(user_context: dict)` and `revoke_access(external_id: str)`, while preserving backward-compatible keyword and positional parameter handling.
- **Sandbox Mock Refactoring (`backend/app/integrations/github_mock.py`)**:
  - Converted `GitHubMockAdapter` to return typed `AdapterResult` on all execution paths (success, simulated failure, revocation, and health check).
  - Wired active fault-injection simulation for `ProviderConnectionTimeoutError` and `ProviderAuthenticationError`.
- **Secondary Multi-Provider Adapter (`backend/app/integrations/slack_mock.py`)**:
  - Implemented network-free, sandbox-only `SlackMockAdapter` simulating workspace channel and member lifecycle.
  - Registered under `ProviderAdapterFactory.register_provider("slack", SlackMockAdapter)`.
  - Supports directive `user_context` and `external_id` signatures plus typed exception fault injection.
- **Domain Service Alignment (`backend/app/services/access.py`)**:
  - Upgraded `AccessService.provision_request` and `revoke_request` to consume typed `AdapterResult` attributes directly (`result.success`, `result.status`, `result.external_id`, `result.error_message`).
  - Added explicit handling for `ProviderConnectionTimeoutError` and `ProviderAuthenticationError` ensuring failed state transitions without leaking internal traces.
  - Restricted `result.to_dict()` strictly to audit ledger logging and response metadata.
- **Typed Exception Hierarchy (`backend/app/integrations/exceptions.py`)**:
  - Established `ProviderConnectionTimeoutError` and `ProviderAuthenticationError` subclassing `ProviderIntegrationError` without internal credential leakage.
  - Documented future live integration wiring (HTTP 408/504 and 401/403) and verified active raising in mock adapters.
- **Verification & Invariants**:
  - Zero edits to `backend/app/api/` or `backend/app/models/` (100% external REST contract stability).
  - All 10 backend regression test suites + Next.js frontend production build verified 100% green.

### ✅ Task P-02: Repository Pattern Implementation (DWOP Engineering Execution Plan 3.2)
- **BaseRepository Generic CRUD (`backend/app/repositories/base.py`)**:
  - Strongly typed `BaseRepository[ModelType]` providing `get_by_id`, `list_paginated`, `create`, `update`, `delete`, `count`, and `exists`.
  - Mandatory tenant isolation routing: every public query routes strictly through `_scoped_query(tenant_id)`.
  - Non-committing mutation semantics: repositories stage and flush (`db.flush()`), NEVER committing transactions.
  - Robust `update(tenant_id, id, obj_in)` supporting both Pydantic `BaseModel` (via `model_dump(exclude_unset=True)`) and `dict` with `hasattr` guards.
- **Eight Domain Repositories (`backend/app/repositories/`)**:
  1. `UserRepository`: identity lookups, global email/id resolution for auth challenge & JWT validation, role filtering.
  2. `ProfessionalRepository`: workforce directory filtering, engagement association, talent intake cohort staging.
  3. `OrganizationRepository` *(approved 8th extension)*: Department & Team entities, hierarchy traversal, cycle prevention ancestor lookups.
  4. `ProjectRepository`: commercial Client accounts, delivery projects, project code lookups.
  5. `OnboardingRepository`: blueprint templates, checklist template items, run instantiation, concrete checklist items.
  6. `AssignmentRepository`: capacity allocations, active percentage sums (`sum_active_capacity`), strict bounded context (zero foreign entity getters).
  7. `AccessRepository`: tool integrations, access request lifecycle, approval decisions.
  8. `AuditRepository`: append-only immutable event logging, chronological timeline queries, immutability guards (`NotImplementedError` on update/delete).
- **Service Layer & Unit of Work Alignment**:
  - Domain services (`PeopleService`, `OrganizationService`, `OnboardingService`, `AssignmentService`, `AccessService`, `AuditService`) wired to repositories with optional default injection (`repo or XRepository(db)`), preserving 100% router contract compatibility.
  - `AssignmentService` injects `assignment_repo`, `project_repo`, `professional_repo`, and `org_repo` for cross-domain existence checks without repository cross-contamination.
- **Auth Dependency Isolation**:
  - `backend/app/core/dependencies.py` and `backend/app/api/auth.py` updated to consume `UserRepository` for identity lookups with zero changes to REST contracts.
- **Automated Verification (`backend/scripts/test_dwop014_repositories.py`)**:
  - Suite 10 added, comprehensively validating generic CRUD, multi-tenant isolation (Tenant A data 100% invisible to Tenant B), Unit of Work non-committing flushes, and all 8 domain repository interfaces.

### ✅ Task P-05: Facade Pattern Implementation (DWOP Engineering Execution Plan 3.5)
- **WorkforceOnboardingFacade (`backend/app/facades/workforce.py`)**:
  - Introduces `WorkforceOnboardingFacade` to coordinate workforce intake, template onboarding run instantiation, baseline tool access requests, and immutable audit logging within a single atomic database transaction boundary.
  - Added optional `commit: bool = True` to `PeopleService.create_person`, `OnboardingService.start_onboarding_run`, and `AccessService.create_request` while preserving 100% default backward compatibility.
  - Implemented `ToolAccessSpec` and automatic integration provider defaults (`github` -> `repository`, `slack` -> `channel`, `trello` -> `board`, `google_workspace`/`m365` -> `drive`).
  - Automated verification via `backend/scripts/test_dwop015_facade.py` (Suite 11) confirming multi-domain atomic persistence, mid-transaction rollback, and cross-tenant failure isolation.

### ✅ Task P-06: State Machine Pattern Implementation (DWOP Engineering Execution Plan 3.6 & 4.3)
- **Generic Base State Machine (`backend/app/core/state_machines.py`)**:
  - Strongly typed `BaseStateMachine[StateType]` providing declarative transition graphs, condition guards, idempotent same-state checks, and terminal state protections.
  - Exception hierarchy inheriting from `ValueError` (`StateMachineError`, `InvalidStateTransitionError`, `TransitionGuardError`) ensuring stable HTTP 400 Bad Request API contracts.
- **Five Domain State Machines**:
  1. `AccessRequestStateMachine`: D-1 reconciled against live `AccessRequestStatus` enum (`requested`, `approved`, `provisioning`, `provisioned`, `failed`, `revoked`). Enforces approver identity for `approved`, external provider reference for `provisioned`, error rationale for `failed`, and terminal absorbing states for `failed` and `revoked`.
  2. `AssignmentStateMachine`: D-2 reconciled against live `AssignmentStatus` enum (`active` -> `completed` / `reassigned`; terminal protection prevents reactivation).
  3. `OnboardingRunStateMachine`: D-3 reconciled against live run statuses (`in_progress`, `blocked`, `completed`; `pending` reserved). Enforces 100% checklist completion guard for `completed` and allows `blocked` -> `completed` recalculation consistency.
  4. `OnboardingItemStateMachine`: D-4 extension enforcing non-empty `blocker_reason` guard for `blocked` state and evidence checks for `completed` state.
  5. `TicketStateMachine`: Staged in passive mode per §3 Task 3.6 & §4 Task 4.3 across 6 delivery board stages (`backlog`, `todo`, `in_progress`, `blocked`, `review`, `completed`), requiring non-empty `blocked_reason` and supervisory credentials (`ADMIN` / `MANAGER`) to complete review.
- **Domain Service Wiring**:
  - `AccessService`: Replaces ad-hoc `_ALLOWED_TRANSITIONS` with `AccessRequestStateMachine` and aliases `AccessLifecycleError(InvalidStateTransitionError)` to preserve exception contracts.
  - `OnboardingService`: Enforces `OnboardingItemStateMachine` transition guards (rejecting missing `blocker_reason` with HTTP 400) and `OnboardingRunStateMachine` status recalculation.
  - `AssignmentService`: Enforces `AssignmentStateMachine` preventing mutation of terminal assignments with HTTP 400.
- **Automated Verification (`backend/scripts/test_dwop016_state_machine.py`)**:
  - Suite 12 added, verifying generic FSM rules, all 5 domain state machines, condition guards, and domain service HTTP 400 integration contracts.

### ✅ Task O-01: Stateless RBAC Policy Engine (ADR-002) — **GATE 2 EXECUTED**
**Milestone**: Gate 2 Execution — Policy architecture packaged and token claim structures shipped.

#### Phase 1 — Security & Token Payload Refactoring (`backend/app/core/security.py`)
- Access JWT now cryptographically embeds the user's **verified `role`** claim (resolved server-side at login, never from client input).
- Access JWT now embeds the **`tenant_id`** claim, which is load-bearing: a mismatch between the claim and the authoritative user row is rejected with `401`, so the claim can no longer be decorative.
- Access JWT now embeds the user's specific **`permissions`** claim — a fully expanded, sorted permission list resolved from the in-memory policy matrix.
- Added `iat`, `jti`, `iss` and `aud` claims; `decode_access_token` now verifies issuer and audience in addition to the signature, so tampered payloads are rejected outright.
- New `Settings`: `TOKEN_ISSUER`, `TOKEN_AUDIENCE`, `REFRESH_TOKEN_EXPIRE_DAYS` (reserved for the O-05 fully-stateless path).

#### Phase 2 — In-Memory Policy Engine (`backend/app/core/policy.py` — NEW)
- **`PolicyEngine` class** evaluating authorization strictly in application memory. It accepts no database session, no cache handle and no HTTP client — resolution is a dict lookup plus `frozenset` membership tests.
- **`Permission` catalogue** (37 permissions, `<domain>:<action>[:<qualifier>]` grammar with `:all` ownership scoping) and a **frozen policy matrix**: `MEMBER` (12) ⊂ `MANAGER` (23) ⊂ `ADMIN` (37). Roles are additive by construction.
- Evaluated against the **cryptographically signed claims** extracted from the JWT, **eliminating all per-endpoint database lookups for permissions**.
- **Tenant boundary checks strictly retained** and evaluated *before* permission membership — a broader role never authorizes a cross-tenant read.
- **Fail-closed by construction**: missing role, unknown role, missing tenant claim and unknown resource tenant are all denials.
- Measured policy resolution: **~17 µs per evaluation** over 20,000 consecutive calls (sub-millisecond by a factor of ~50).

#### Phase 3 — Hybrid Offboarding Guard (Dependency / Middleware Pipeline)
- **Exactly one lightweight database query per authenticated request** (`UserRepository.get_lifecycle_flags`, `users` ⋈ `tenants`, narrow `load_only` projection that never fetches `hashed_password`).
- Simultaneously verifies **`User.is_active`** (instant revocation for offboarded professionals) **and `Tenant.is_active`** (parent workspace validity).
- **New `Tenant.is_active` column** + migration `backend/alembic/versions/0003_tenant_lifecycle_guard.py`, plus composite index `ix_users_tenant_id_is_active`.
- While the database handles revocation, **all RBAC permission computing stays in the in-memory engine** — zero permission queries remain.
- RBAC dependencies now expose factories (`require_permissions`, `require_any_permission`, `require_roles`, `enforce_tenant_boundary`) plus pre-composed guards, with `require_admin` / `require_admin_or_manager` retained as backwards-compatible aliases.

#### Phase 4 — Architectural Decision Record (`docs/adr-002-stateless-rbac-scaling.md`)
- ADR-002 authored documenting the shift to stateless RBAC, refining ADR-001 Trigger 3 and its "Caching: None" baseline.
- **Selected architecture defined**: an **In-Memory Policy Matrix embedded in application memory that evaluates signed JWT claims, delivering sub-millisecond policy resolution with zero infrastructure dependencies.**
- **Future scaling path** to fully-stateless **fifteen-minute tokens using refresh-token rotation**, sequenced across O-01 → O-05.
- **Alternatives Considered** section formally rejecting:
  - **Distributed Redis caching** — unwarranted infrastructure overhead, external network latency hops (20–50× slower than the in-memory lookup it replaces), and cache-invalidation race conditions during membership changes where a `DEL` racing a `SET` can resurrect a revoked grant across replicas.
  - **Open Policy Agent (OPA) / external engines** — heavy daemon deployment complexity, sidecar overhead, and operational maintenance burdens (second language, second release train, second datastore for decision logs) for a 3-role matrix.
  - Also recorded: DB-backed permission tables, JWT denylists, Casbin/`permify` libraries, and pure statelessness without revocation.

#### Phase 5 — Governance & Sign-Off
- Policy architecture code and the new token claim structures are packaged and integrated.
- New endpoint `GET /api/v1/auth/policy` exposes the caller's effective in-memory-resolved policy for client-side RBAC navigation.
- `POST /api/v1/auth/login` and `/auth/refresh` now return the resolved `permissions` list; login also refuses to mint tokens into a suspended tenant.
- Service-layer and state-machine role checks (`AccessService`, `OnboardingService`, `TicketStateMachine` supervisory guard) routed through `PolicyEngine`, eliminating duplicated string-literal role comparisons.
- **Automated Verification (`backend/scripts/test_dwop017_stateless_rbac.py`)** — Suite 13 added: **41/41 assertions green**, covering matrix resolution, fail-closed evaluation, tenant boundary retention, signed/tampered claim handling, single-query enforcement (asserted at the SQL level), offboarded-professional revocation and tenant-suspension revocation.
- All 12 pre-existing regression suites remain **100% green**.

---

### ✅ Task O-02: RBAC Permission Matrix Publication & Team Lead Derived Scope — **GATE 2 SUBMITTED**
**Milestone**: Gate 2 Submission — single authoritative permission matrix published, team-lead authority derived as a scope, and documentation locked to code by a build gate.

#### Phase 1 — Authoritative Matrix Publication (`docs/rbac-matrix.md` — NEW)
- Published the **single authoritative, audit-ready permission matrix** governing all system operations, covering all **37 canonical permissions** with per-permission functional definitions, plus the capability domains (`tenant`, `departments`, `teams`, `clients`, `projects`, `people`, `onboarding`, `assignments`, `access`, `integrations`, `audit`, `users`).
- Standardised **tenant-wide security rules**: mandatory tenant isolation (evaluated before role breadth, never delegated to role width), instant revocation via the single per-request hybrid guard, fail-closed behaviour table, claim integrity, and an explicit segregation-of-duties table (Administrator-only bulk import, revocation, blueprint authoring and team-lead assignment; direct-report constraint on Manager approvals).
- Matrix counts published and asserted: `MEMBER` (12) ⊂ `MANAGER` (23) ⊂ `ADMIN` (37), strictly nested.

#### Phase 2 — Team Lead as a Derived Scope (`backend/app/core/scopes.py` — NEW)
- **Team Lead authority is a derived scope, not a fourth global role.** It is absent from `UserRole` (`ADMIN`, `MANAGER`, `MEMBER` only), is never written to `users.role`, cannot be self-assigned, and required **zero schema migrations** — `teams.team_lead_id` already existed.
- `ScopeResolver` derives the `team_lead` scope and its `lead_teams` bindings from `Team.team_lead_id` at token issuance (`POST /auth/login`, `POST /auth/refresh`); the `ScopeResolver`/`ScopeGrant` result is frozen, typed, and serialised into the signed JWT as `scopes` and `lead_teams` claims.
- Resolution stays **stateless and in-memory** at authorization time — the claims are authoritative, so a request costs no extra database round-trip.

#### Phase 3 — Engine & Enforcement Synchronisation (`app/core/policy.py`, `dependencies.py`, `services/`)
- **Every documented permission is mapped directly into the `PolicyEngine` configuration tables** (`POLICY_MATRIX`, `SCOPE_MATRIX`, `RESOURCE_BOUND_SCOPES`) — no endpoint defines its own permission strings.
- Permission identifiers standardised to **operational formats** across the engine, dependencies, services and suites (`people:read`, `assignments:allocate`, `access:approve`, `audit:export`). A read-side alias table (`LEGACY_PERMISSION_ALIASES`, 33 entries) preserves in-flight O-01 tokens through a rolling deploy; newly issued tokens carry only canonical strings.
- Added `enforce_scope_boundary`, the only path to scope-granted authority. It requires the team identifier the endpoint **loaded from the database** — a client-supplied `team_id` query parameter was explicitly evaluated and rejected during design, so no request-controlled value participates in an authorization decision.
- Evaluation order fixed and tested as **tenant boundary → role breadth → scope breadth**, making Team Lead authority strictly narrower than the Manager authority it overlaps, and failing closed when a scope-restricted evaluation receives no resource team.
- `GET /api/v1/auth/policy` now separates `permissions` (role) from `effective_permissions` (role ∪ scope) and publishes `scopes`, `lead_teams`, `is_team_lead`, `scope_boundaries_enforced` and `authority_reference`; `TokenResponse` mirrors the scope claims.

#### Phase 4 — Documentation Locked To Code As A Build Gate (`test_dwop018_rbac_matrix.py` — NEW)
- Suite 14 added: **57/57 assertions green**. It parses every capability table in `docs/rbac-matrix.md`, compares each granted column against the engine tables, asserts the reverse direction (no unpublished permission, no unresolvable permission), and fails the build on any divergence — so the document cannot drift from the code silently.
- Also verified: strict nesting and counts, no `*` sentinel grant, Team Lead inexpressible as a stored role, identifier-format conformance, legacy alias resolution, scope derivation from `Team.team_lead_id`, own-team allow / foreign-team deny / cross-tenant deny / no-team fail-closed, claim tamper rejection, and refresh-time propagation of scope loss.

#### Phase 5 — Regression, Governance & Packaging
- **All 14 verification suites green** (`test_default_github_integration_seed`, Suites 1–14; **198 measured assertions** across the suites that report `[PASS]` counters), plus `alembic upgrade head → downgrade -1 → upgrade head` verified against a clean database.
- Fixed a latent test-isolation defect in `test_dwop013_audit_timeline.py`: the integration lookup was unscoped (`db.query(Integration).first()`), so it resolved an integration belonging to whichever tenant happened to be seeded first and failed whenever the database held more than one tenant. It is now tenant-scoped.
- ADR-002 amended (§6.1) and this report updated to **v1.4**; deliverables packaged for formal **Khalifa security review** and Gate 2 clearance.

---


## 4. API Endpoint Matrix & Frontend Consumption Status

| HTTP Method | Endpoint Path | RBAC / Auth Guard | Ticket Mapping | Frontend Consumption Status |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Public | DWOP-004 | ✅ Consumed in `frontend/src/app/login/page.tsx` & `AuthContext` |
| `GET` | `/api/v1/auth/me` | Authenticated (`get_current_active_user`) | DWOP-004 | ✅ Consumed in `frontend/src/contexts/AuthContext.tsx` |
| `GET` | `/api/v1/auth/policy` | Authenticated (in-memory policy + derived-scope resolution) | O-01, O-02 | ✅ Ready (drives client-side RBAC navigation; publishes role vs. effective authority, scopes and lead-team bindings) |
| `GET` | `/api/v1/departments` | Authenticated | DWOP-003 | ⏳ Queued for Org Management UI |
| `POST` | `/api/v1/departments` | `require_admin` | DWOP-003 | ⏳ Queued for Org Management UI |
| `GET` | `/api/v1/departments/{id}` | Authenticated | DWOP-003 | ⏳ Queued for Org Management UI |
| `GET` | `/api/v1/teams` | Authenticated | DWOP-003 | ⏳ Queued for Org Management UI |
| `POST` | `/api/v1/teams` | `require_admin` | DWOP-003 | ⏳ Queued for Org Management UI |
| `GET` | `/api/v1/people` | Authenticated | DWOP-005 | ✅ Consumed in `frontend/src/app/(authenticated)/workforce/page.tsx` |
| `POST` | `/api/v1/people` | `require_admin_or_manager` | DWOP-005 | ⏳ Queued for Add Talent Modal |
| `GET` | `/api/v1/people/{id}` | Authenticated | DWOP-005 | ✅ Consumed in `frontend/src/app/(authenticated)/workforce/[id]/page.tsx` |
| `POST` | `/api/v1/people/bulk-import` | `require_admin` | DWOP-005 | ⏳ Queued for Bulk Import Modal |
| `GET` | `/api/v1/onboarding/templates` | Authenticated | DWOP-006 | ⏳ Queued for Onboarding Setup UI |
| `POST` | `/api/v1/onboarding/templates` | `require_admin` | DWOP-006 | ⏳ Queued for Onboarding Setup UI |
| `POST` | `/api/v1/onboarding/runs` | `require_admin_or_manager` | DWOP-006 | ⏳ Queued for Trigger Onboarding Action |
| `GET` | `/api/v1/onboarding/runs` | Authenticated | DWOP-006/Alignment | ✅ Ready (wired for `workforce/[id]` runs listing) |
| `GET` | `/api/v1/onboarding/runs/{run_id}` | Authenticated | DWOP-006 | ⏳ Queued for `/onboarding/[run_id]` UI |
| `PATCH` | `/api/v1/onboarding/runs/{run_id}/items/{item_id}` | Admin / Manager / Assigned Prof | DWOP-006 | ⏳ Queued for Checklist Interactive Tasks |
| `GET` | `/api/v1/assignments/projects` | Authenticated | DWOP-003/009 | ⏳ Queued for Project Selector |
| `POST` | `/api/v1/assignments/projects` | `require_admin` | DWOP-003/009 | ⏳ Queued for Project Creation Modal |
| `GET` | `/api/v1/assignments/capacity` | Authenticated | DWOP-009 | ⏳ Queued for Capacity Dashboard |
| `GET` | `/api/v1/assignments/capacity/professionals/{id}` | Authenticated | DWOP-009 | ⏳ Queued for Profile Allocation Breakdown |
| `POST` | `/api/v1/assignments/allocate` | `require_admin_or_manager` | DWOP-009 | ⏳ Queued for Allocate Talent Modal |
| `GET` | `/api/v1/assignments` | Authenticated | DWOP-009 | ⏳ Queued for Allocations Grid |
| `GET` | `/api/v1/assignments/my-allocations` | Authenticated | DWOP-009 | ⏳ Queued for Personal Projects View |
| `PATCH` | `/api/v1/assignments/{id}` | `require_admin_or_manager` | DWOP-009 | ⏳ Queued for Capacity Modification |
| `GET` | `/api/v1/access/requests` | Authenticated (Members restricted to own) | DWOP-010 | ⏳ Queued for Access Management UI |
| `POST` | `/api/v1/access/requests` | Authenticated | DWOP-010 | ⏳ Queued for Request Access Modal |
| `POST` | `/api/v1/access/requests/{id}/approve` | Admin or Manager (direct report) | DWOP-010 | ⏳ Queued for Manager Approval Portal |
| `POST` | `/api/v1/access/requests/{id}/provision` | `require_admin_or_manager` | DWOP-010 | ⏳ Queued for Provisioning Action |
| `POST` | `/api/v1/access/requests/{id}/revoke` | `require_admin` | DWOP-010 | ⏳ Queued for Security Revocation Panel |
| `GET` | `/api/v1/access/requests/{id}/status` | Authenticated | DWOP-010 | ⏳ Queued for Access Status Polling |
| `GET` | `/api/v1/audit/logs` | `require_admin` | DWOP-013 | ⏳ Queued for Executive Activity Timeline UI |
| `GET` | `/api/v1/audit/export` | `require_admin` | DWOP-013 | ⏳ Queued for Compliance Export Button |

---

## 5. Current Seed Data Reference

The database seed script ([`backend/scripts/seed_org_structure.py`](file:///c:/Users/walid/OneDrive/Documents/Work/dwop-platform/backend/scripts/seed_org_structure.py)) provisions:

### 1. Tenant
- **Name**: `AZM Nexus`
- **Slug**: `azm-nexus`
- **Plan Tier**: `enterprise`
- **Branding**: `{"theme": "diamond_sapphire", "primary_color": "#2563EB", "accent_shimmer": "#38BDF8"}`

### 2. Users (All Passwords Bcrypt Hashed)
| Email | Password | Role | Permissions |
|---|---|---|---|
| `admin@azm-nexus.com` | `Admin123!` | `ADMIN` | Global governance, template authoring, bulk import, all mutations |
| `atanda.david@azm-nexus.com` | `LeadAtanda2026!` | `ADMIN` | Systems architect, department/project creation, template authoring, bulk import |
| `manager@azm-nexus.com` | `Manager123!` | `MANAGER` | Department oversight, single candidate intake, onboarding management |
| `member@azm-nexus.com` | `Member123!` | `MEMBER` | Self-service profile, checklist item completion (writes blocked with 403) |

### 3. Organizational Structure
- **Departments**:
  - `Executive Leadership` (Manager: Admin)
  - `Core Platform & Engineering` (Parent: Executive Leadership, Manager: Atanda David)
- **Teams**:
  - `Backend & Cloud Architecture` (Department: Core Platform, Lead: Atanda David)
  - `Frontend & Workforce Experience` (Department: Core Platform)
- **Client**: `Apex Global Banking Group`
- **Project**: `DWOP Platform Foundation` (`DWOP-CORE`)

### 4. Seeded Professionals (Intake Cohort)
1. **Jane Doe** (`jane.doe@azm-nexus.com`): Senior Python/FastAPI/PostgreSQL Engineer (Contractor @ $85/hr)
2. **John Smith** (`john.smith@azm-nexus.com`): Next.js/React/TypeScript Frontend Engineer (Employee @ $90k/yr)
3. **Alice Johnson** (`alice.johnson@azm-nexus.com`): DevOps & Cloud Infrastructure Engineer (Contractor @ $95/hr)

### 5. Walid's Mock Onboarding Template ("Standard Software Engineer v2.1")
| Step # | Task Title | Default Due Days | Evidence Required |
|---|---|---|---|
| 1 | Sign Confidentiality & Non-Disclosure Agreement (NDA) | 1 day | `signed_pdf` |
| 2 | Setup Corporate GitHub & Enforce Hardware 2FA | 2 days | `screenshot` |
| 3 | Complete InfoSec & OWASP Compliance Briefing | 3 days | `none` |
| 4 | Development Environment Setup & Local Docker Run | 4 days | `screenshot` |
| 5 | Team Orientation & Engineering Manager 1:1 Sync | 5 days | `none` |

### 6. Active Demo Onboarding Run (Jane Doe)
- Instantiated against Jane Doe upon database seeding.
- Generates 5 live `OnboardingItem` tasks linked to her profile.
- Demonstrates blocker resolution flow for executive review.

---

## 6. How to Run & Verify

```bash
# 1. Activate backend environment
cd backend
.\venv\Scripts\activate

# 2. Run seed script (idempotent, safe to re-run)
python scripts/seed_org_structure.py

# 3. Start development server
uvicorn app.main:app --reload --port 8000

# 4. Run automated test suites (13 platform regression suites)
python scripts/test_dwop004_auth.py
python scripts/test_dwop005_people.py
python scripts/test_dwop006_onboarding.py
python scripts/test_dwop009_assignments_capacity.py
python scripts/test_dwop010_access_lifecycle.py
python scripts/test_dwop011_adapters.py
python scripts/test_dwop012_github_mock_poc.py
python scripts/test_dwop013_audit_timeline.py
python scripts/test_default_github_integration_seed.py
python scripts/test_dwop014_repositories.py
python scripts/test_dwop015_facade.py
python scripts/test_dwop016_state_machine.py
python scripts/test_dwop017_stateless_rbac.py
```

* **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Frontend Web Application**: [http://localhost:3000](http://localhost:3000)
