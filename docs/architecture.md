# Architecture & API Boundaries (DWOP-002)

Here is the architectural blueprint. The vibecoding agent will use this to set up the FastAPI routers and Next.js routes.

## High-Level Architecture

```mermaid
graph TD
    subgraph Client
        UI[Next.js Frontend / Admin Dashboard]
    end

    subgraph API Gateway / Core
        API[FastAPI Backend]
        Auth[OIDC/RBAC Auth Middleware]
        Tenant[Tenant Context Middleware]
    end

    subgraph Domain Services
        OrgSvc[Organisation & Structure]
        PeopleSvc[People & Intake]
        OnboardSvc[Onboarding Engine]
        AssignSvc[Assignments & Capacity]
        AccessSvc[Access Request Lifecycle]
        AuditSvc[Audit & Governance]
    end

    subgraph Integration Layer (Adapter Pattern)
        Adapter[Provider Adapter Interface]
        GH[GitHub/GitLab Adapter]
        Trello[Trello Adapter]
        Slack[Slack Adapter]
    end

    subgraph Data & Async
        DB[(PostgreSQL)]
        Jobs[Background Jobs / Webhooks]
    end

    UI -->|HTTPS| API
    API --> Auth
    API --> Tenant
    API --> OrgSvc & PeopleSvc & OnboardSvc & AssignSvc & AccessSvc & AuditSvc
    OrgSvc & PeopleSvc & OnboardSvc & AssignSvc & AccessSvc --> DB
    AccessSvc --> Adapter
    Adapter --> GH & Trello & Slack
    AuditSvc --> DB
    Jobs --> DB
```

## Core API Boundaries (FastAPI Routers)

Exact router files in `backend/app/api/`:

- **`auth.py`** - Login, token refresh, user profile.
- **`tenants.py`** - Organization/Workspace management.
- **`people.py`** - Professionals, bulk import, profiles.
- **`onboarding.py`** - Templates, runs, checklist items.
- **`assignments.py`** - Projects, teams, capacity allocation.
- **`access.py`** - Access requests, approvals, provisioning states.
- **`audit.py`** - Activity timeline, audit logs.
- **`integrations.py`** - Connected services, webhook receivers.

## Strict Non-Singleton Invariant — Database Sessions

Application configuration may be process-scoped, and the provider adapter registry infrastructure (registered provider-class mappings) may be process-scoped. Neither scope extends to tenant-specific adapter objects or database sessions.

Every database `Session` must be created on demand for one request or unit of work and closed when that request completes. Sessions must never be stored as process-global state, cached, reused across concurrent requests, or passed between worker threads. The database engine and session factory are process-level infrastructure only; each `SessionLocal()` call must produce an independently scoped SQLAlchemy `Session`.

Violating this invariant risks cross-tenant data leakage, transaction bleeding between requests, unsafe concurrent use of SQLAlchemy `Session` objects, stale transactional state, and connection or other resource exhaustion. This separation preserves DWOP's tenant isolation boundary while allowing safe process-scoped configuration and registry metadata.
