# DWOP Platform — Sprint 0 Engineering & Architecture Progress Report

**Document Version**: 1.2 (Sprint 0 / Assignments & Capacity Allocation Engine Milestone)  
**Organization**: AZM Nexus Limited  
**System**: Digital Workforce Operations Platform (DWOP)  
**Status**: Completed through Ticket DWOP-009 (including DWOP-010 through DWOP-013, and DWOP-007/008 frontend)  


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
  - All 9 backend regression test suites + Next.js frontend production build verified 100% green.


---


## 4. API Endpoint Matrix & Frontend Consumption Status

| HTTP Method | Endpoint Path | RBAC / Auth Guard | Ticket Mapping | Frontend Consumption Status |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Public | DWOP-004 | ✅ Consumed in `frontend/src/app/login/page.tsx` & `AuthContext` |
| `GET` | `/api/v1/auth/me` | Authenticated (`get_current_active_user`) | DWOP-004 | ✅ Consumed in `frontend/src/contexts/AuthContext.tsx` |
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

# 4. Run automated test suites
python scripts/test_dwop004_auth.py
python scripts/test_dwop005_people.py
python scripts/test_dwop006_onboarding.py
python scripts/test_dwop009_assignments_capacity.py
python scripts/test_dwop010_access_lifecycle.py
python scripts/test_dwop011_adapters.py
python scripts/test_dwop012_github_mock_poc.py
python scripts/test_dwop013_audit_timeline.py
```

* **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Frontend Web Application**: [http://localhost:3000](http://localhost:3000)
