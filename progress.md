# DWOP Platform — Sprint 0 Engineering & Architecture Progress Report

**Document Version**: 1.0 (Sprint 0 / Foundation Milestone)  
**Organization**: AZM Nexus Limited  
**System**: Digital Workforce Operations Platform (DWOP)  
**Status**: Completed through Ticket DWOP-006  

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

---

## 4. Current Seed Data Reference

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

## 5. How to Run & Verify

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
```

* **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Frontend Web Application**: [http://localhost:3000](http://localhost:3000)
