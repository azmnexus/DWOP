# DWOP Platform — Engineering Team Handover & Synchronization Guide

**Document Version**: 1.0  
**Date**: September 7, 2026  
**Organization**: AZM Nexus Limited  
**System**: Digital Workforce Operations Platform (DWOP)  
**Acting Project Lead**: Walid (covering Atanda David, partially covering Khalifa)  

---

## 1. Team Structure & Functional Ownership Breakdown

| Team Member | Role & Coverage | Scope of Ownership | Authoritative Directory | Primary Tickets |
|---|---|---|---|---|
| **Walid** | Acting Project Lead & Core Backend Co-Dev | Project orchestration, architectural compliance, code review, test harness verification, core services | `backend/app/` & repository root | DWOP-001–006, DWOP-009, Review & Integration |
| **Khalifa (`KHALIFAH334`)** | Technical Supervisor & Core Backend | Core backend architecture oversight (between university exams), audit timeline, database engine | `backend/app/` | Supervisor review, Entities 17/18, DWOP-013 architecture |
| **Usman (`UsmanBala-cyber`)** | Frontend Engineering Lead | Next.js 14 App Router, Diamond Glass design system, client-side state, API consumption | `frontend/src/` | DWOP-007, DWOP-008, DWOP-014, DWOP-015 |
| **Oladotun (`Oladotun1`)** | Integrations & Adapters Lead | Third-party provider adapter framework, access request lifecycle, mock & live connectors | `backend/app/integrations/` & `backend/app/services/access.py` | DWOP-010, DWOP-011, DWOP-012, Slack/Trello adapters |

---

## 2. Directory Ownership & Architectural Boundaries

> [!IMPORTANT]
> **CRITICAL REPOSITORY STRUCTURE RULE (Section 5 of the Implementation Directive)**:
> All backend code MUST reside strictly inside the `backend/app/` package hierarchy. 
> Creating package directories directly under `backend/` (e.g. `backend/models`, `backend/services`, `backend/api`) breaks Python pathing, Docker configurations, and multi-tenant middleware imports.

```text
dwop-platform/
├── docs/                                  # Locked specifications (erd.md, architecture.md, api-contracts.md)
├── backend/
│   ├── app/                               # [AUTHORITATIVE BACKEND ROOT - DO NOT BYPASS]
│   │   ├── api/                           # FastAPI routers (auth, people, onboarding, access, audit, assignments)
│   │   ├── core/                          # Config, Database engine, JWT Auth, Multi-Tenancy Middleware
│   │   ├── models/                        # Declarative SQLAlchemy models (Entities 1 to 19 per erd.md)
│   │   ├── schemas/                       # Pydantic v2 schemas for request validation and serialization
│   │   ├── services/                      # Domain logic services (AuditService, AccessService, etc.)
│   │   └── integrations/                  # Provider Adapter Pattern (BaseProviderAdapter, GitHub, Slack)
│   ├── alembic/                           # Database migration scripts
│   ├── scripts/                           # Database seeding and standalone integration test runners
│   └── tests/                             # Pytest suite
└── frontend/
    ├── src/                               # [AUTHORITATIVE FRONTEND ROOT]
    │   ├── app/                           # Next.js 14 App Router routes ((authenticated), login)
    │   ├── components/                    # UI Design System (Diamond Glass: Button, Card, Badge, Modal)
    │   ├── contexts/                      # React Contexts (AuthContext)
    │   ├── lib/                           # Centralized Axios/fetch API client and auth helpers
    │   └── types/                         # TypeScript interfaces matching backend Pydantic schemas
    └── public/                            # Static brand assets and SVG icons
```

---

## 3. Current Integration Status: What's Live vs. What's Mocked

### Live & Verified Backend Services (`backend/app/`)
1. **Multi-Tenancy Context & Isolation**: Every request is scoped by tenant. All queries and write operations enforce `tenant_id` automatically from the request JWT.
2. **Auth & RBAC**: Real bcrypt password hashing and JWT issuance (`POST /api/v1/auth/login`). Admin/Manager/Member permissions strictly enforced with HTTP 403 blocks.
3. **People & Cohort Intake Engine**: Single candidate intake and atomic batch intake (`POST /api/v1/people/bulk-import`) with transactional rollback on duplicate emails.
4. **Onboarding Workflow Engine**: Role blueprints, calculated deadline task instantiation, blocker justification, and completion advancement to `ready` status.
5. **Access Request Lifecycle Engine**: Request submission, manager approval (restricted to direct reports), admin revocation, and state transitions.
6. **Immutable Audit Ledger & Timeline**: Append-only `audit_events` (Table 19) recording all mutations with actor, action, target, metadata, and timestamps. Filterable and exportable.
7. **Database Fallback**: Automated fallback from PostgreSQL (`5432`) to SQLite (`dwop.db`) for offline/local development without code changes.

### Live & Verified Frontend (`frontend/src/`)
1. **Diamond Glass Design System**: Glassmorphic styling, dark sapphire glowing accents, responsive CSS modules, zero ad-hoc CSS.
2. **App Shell**: Responsive `AppHeader`, desktop `Sidebar`, mobile slide-out `MobileDrawer`, and route guards in `middleware.ts`.
3. **Authentication Flow**: Real JWT login against `/api/v1/auth/login`, persistent session hydration, and demo credential quick-fill.
4. **Workforce Directory (`/workforce`)**: Live search, status filters, talent grid, and direct API consumption from `/api/v1/people`.
5. **Professional Profile (`/workforce/[id]`)**: Deep-dive profile tabs, skills, availability badges, and engagement contract details.

### What is Mocked / Sandbox
1. **GitHub Provider Adapter**: Network-free mock (`network_io = False`) that simulates team/repo invites in an in-memory dictionary.
2. **Slack & Trello Adapters**: Stubs ready for implementation following `BaseProviderAdapter`.

---

## 4. Special Reconciliation Instructions for Khalifa (`KHALIFAH334`)

> [!WARNING]
> **ATTENTION KHALIFA — RECONCILIATION PROTOCOL FOR REMOTE COMMITS**:
> Commits `0df9e51` through `43e81c6` pushed directly to `origin/development` created parallel backend directories (`backend/models/`, `backend/services/`, `backend/api/`) outside of `backend/app/`. This diverges from Section 5 of our locked Engineering Implementation Directive.
>
> **Do NOT push additional commits directly to `origin/development` without a branch PR.**

### How to Reconcile Your Work Without Conflicts:
1. **Authoritative State**: The authoritative, tested, and fully integrated codebase is maintained under `backend/app/*` on the `development` branch.
2. **Audit Service Reconciliation**:
   - The centralized `AuditService` and `AuditEvent` (Table 19) have already been fully built, retroactively wired to all existing modules, and verified with 100% passing tests (`backend/scripts/test_dwop013_audit_timeline.py`).
   - You do not need to rewrite the Audit engine.
3. **Your Next Focus Area (Supervisory / Entities 17 & 18)**:
   - Please review the locked ERD for **Entity 17 (`DOCUMENT_ACKNOWLEDGEMENT`)** and **Entity 18 (`NOTIFICATION`)**.
   - When developing support for Entity 17 or 18, please create an isolated feature branch (e.g. `feature/khalifa-governance`).
   - Ensure all models are placed inside `backend/app/models/`, schemas in `backend/app/schemas/`, and routers in `backend/app/api/`.

---

## 5. Team Next Tasks & Action Plan

### 👨‍💻 Usman (Frontend)
- [x] **DWOP-007**: Diamond Glass design system, App Shell, Login screen (**Done & Merged**).
- [x] **DWOP-008**: Workforce Directory & Profile View (**Done & Merged**).
- [ ] **DWOP-014 (Next Priority)**: Onboarding Interactive Portal (`/onboarding` and `/onboarding/[id]`).
  - Wire to `GET /api/v1/onboarding/templates` and `GET /api/v1/onboarding/runs`.
  - Implement task checklist checkboxes calling `PATCH /api/v1/onboarding/runs/{run_id}/items/{item_id}`.
  - Implement blocker modal to prompt for `blocker_reason`.
- [ ] **DWOP-015**: Access Request Management View (`/access`).
  - Request tool access modal calling `POST /api/v1/access/requests`.
  - Manager approval cards calling `POST /api/v1/access/requests/{id}/approve`.

### 👨‍💻 Oladotun (Integrations)
- [x] **DWOP-010**: Access Request Lifecycle backend (**Done, Reviewed & Remediated**).
- [x] **DWOP-011**: Provider Adapter Framework (`BaseProviderAdapter`, factory) (**Done & Merged**).
- [x] **DWOP-012**: GitHub Sandbox Mock POC (**Done & Merged**).
- [ ] **Next Task (Slack / Google Workspace Mock Adapters)**:
  - Implement `SlackMockAdapter` in `backend/app/integrations/slack.py` extending `BaseProviderAdapter`.
  - Support `channels:write`, `users:read` mock actions with idempotent invites and revocations.
  - Register in `backend/app/integrations/factory.py`.

### 👨‍💻 Walid (Acting Project Lead / Core Backend)
- [x] Review and remediate DWOP-010/011/012.
- [x] Complete DWOP-013 (Audit Service, Timeline API, retroactive hooks).
- [x] Synchronize and verify Usman's frontend (DWOP-007/008) with zero build errors.
- [ ] **DWOP-009 (Current Priority)**: Assignments & Capacity Allocation Engine (Table 9).
  - Implement `Assignment` model, capacity validation rules (max 100% across concurrent active projects), and allocation APIs.

---

## 6. How to Spin Up the Local Environment

### Backend
```bash
cd backend
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Seed database (creates default tenant, admin/manager/member users, and demo cohort)
python scripts/seed_org_structure.py

# Launch FastAPI
uvicorn app.main:app --reload --port 8000
```
API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

### Frontend
```bash
cd frontend
npm install
npm run dev -- -p 3000
```
Web Application: [http://localhost:3000](http://localhost:3000)

---
*For questions, contact Walid (Acting Project Lead) or post in the DWOP engineering channel.*
