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
