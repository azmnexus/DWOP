# DWOP Platform

Dynamic Workforce Operations Platform (DWOP) — Multi-tenant platform for managing organizations, workforce intake, onboarding workflows, capacity assignments, access provisioning lifecycle, and governance.

## Project Structure

```text
dwop-platform/
├── README.md                 # Project overview, setup, ports, and delivery agreements
├── docs/
│   ├── architecture.md       # System design and API boundaries
│   ├── erd.md                # Data model and relationships (Section 8 compliant)
│   └── api-contracts.md      # Core API endpoints
├── backend/                  # FastAPI + Python
│   ├── app/
│   │   ├── main.py
│   │   ├── core/             # Config, security, multi-tenant context, dependencies
│   │   ├── models/           # SQLAlchemy models (Khalifa's domain)
│   │   ├── schemas/          # Pydantic schemas (Request/Response)
│   │   ├── api/              # FastAPI Routers (Endpoints)
│   │   ├── services/         # Business logic
│   │   └── integrations/     # Provider adapter pattern (Oladotun's domain)
│   ├── alembic/              # DB migrations
│   ├── scripts/              # Seed scripts & automated verification suites
│   ├── requirements.txt
│   └── .env.example
└── frontend/                 # Next.js + React + TS
    ├── src/
    │   ├── app/              # App router (pages)
    │   ├── components/       # UI components
    │   ├── lib/              # API clients, utils
    │   └── types/            # TypeScript interfaces
    ├── package.json
    ├── tsconfig.json
    └── .env.local.example
```

---

## Setup & Getting Started

### 1. Backend (FastAPI)

```bash
cd backend

# Create virtual environment (if not already created)
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# Linux/macOS:
source venv/bin/activate

# Install dependencies (includes email-validator, pydantic, sqlalchemy, python-jose, bcrypt, etc.)
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Run database seed script (also creates a default network-free GitHub integration)
python scripts/seed_org_structure.py

# Run the development server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend (Next.js)

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

---

## Service Endpoints, Ports & Documentation

Once the backend server is running on port **`8000`**, you can access the following in your browser:

| Service / Interface | URL | Description |
|---|---|---|
| **Interactive API Docs (Swagger UI)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Test, authorize, and inspect all endpoints interactively |
| **Alternative API Docs (ReDoc)** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Clean, readable reference documentation |
| **OpenAPI Schema (JSON)** | [http://localhost:8000/api/v1/openapi.json](http://localhost:8000/api/v1/openapi.json) | Raw OpenAPI 3.1 specification |
| **Health Check Endpoint** | [http://localhost:8000/health](http://localhost:8000/health) | Verifies server status & service name |
| **Frontend Web App** | [http://localhost:3000](http://localhost:3000) | Next.js administration portal |

---

## Sprint Foundation Status

### 1. Ticket DWOP-003: Core Organizational Models & Multi-Tenancy (Completed)
- Models: `Tenant` (with `branding` JSONB), `Department`, `Team`, `Client`, `Project`.
- Strict tenant context isolation via `TenantContextMiddleware`.

### 2. Ticket DWOP-004: Authentication Baseline & RBAC (Completed)
- User model with bcrypt password hashing and JWT token issuance via `python-jose`.
- Endpoints:
  - `POST /api/v1/auth/login`: Accepts credentials, returns JWT with `user_id`, `tenant_id`, and `role`.
  - `GET /api/v1/auth/me`: Decodes JWT and returns profile.
- RBAC Dependencies:
  - `get_current_active_user`: Validates JWT, sets tenant context, allows read operations (`GET`).
  - `require_admin`: Restricts write operations (`POST`, `PUT`, `DELETE`) to users with `role: ADMIN`.

### 3. Ticket DWOP-005: People & Intake Engine (Completed)
- Models: `Professional` (with `user_id` FK nullable, `status` enum, `skills` JSONB) and `Engagement` (contractual details).
- Endpoints:
  - `POST /api/v1/people`: Single candidate intake (Requires ADMIN or MANAGER).
  - `GET /api/v1/people`: Scoped directory of talent in tenant.
  - `POST /api/v1/people/bulk-import`: Atomic batch intake of candidates in one transaction (Requires ADMIN).

### 4. Ticket DWOP-006: Onboarding Templates, Runs & Checklist Engine (Completed)
- Models: `OnboardingTemplate`, `OnboardingRun`, `OnboardingItem`.
- Endpoints for template authoring, run instantiation, and item status progression.

### 5. Ticket DWOP-010: Access Lifecycle Provisioning (Completed)
- Models: `Integration` (full Table 14 spec), `AccessRequest`.
- Lifecycle management (requested, approved, provisioned, failed, revoked).

### 6. Ticket DWOP-013 & ERD Gaps (Completed)
- Immutable `AuditEvent` ledger for tracking state changes.
- Automatic audit logging and `Notification` (Table 18) dispatch for governance events.
- `DocumentAcknowledgement` (Table 17) functionality.

### 7. Ticket DWOP-020: Scaling ADR (Completed)
- Documented transition triggers from 10 to 1,000 active users (`docs/adr-001-scaling-10-to-1000.md`).

### Seeded Test Credentials (All Passwords Explicitly Bcrypt Hashed):
| Account | Email | Password | Role | Access Level |
|---|---|---|---|---|
| **Admin** | `admin@azm-nexus.com` | `Admin123!` | `ADMIN` | Full read and write (POST/PUT/DELETE) + Bulk Import |
| **Atanda David** | `atanda.david@azm-nexus.com` | `LeadAtanda2026!` | `ADMIN` | Systems Architect / Super Admin |
| **Manager** | `manager@azm-nexus.com` | `Manager123!` | `MANAGER` | Team lead oversight + Single Professional Intake |
| **Standard Member** | `member@azm-nexus.com` | `Member123!` | `MEMBER` | Read-only (GET); Mutating operations return **403 Forbidden** |

---

## Working Agreement & Domain Ownership

- **Lead & Architecture Gatekeeper**: Atanda David
- **Models, Database & Core APIs (DWOP-003 / DWOP-004 / DWOP-005)**: Khalifa
- **Integrations & Provider Adapters**: Oladotun Fawwaz
- **Operations, Workflows, Checklist Templates & UAT**: Walid
- **Frontend & Workforce Experience UI**: Usman Mubarak
