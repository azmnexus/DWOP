# Core API Contracts (DWOP-API)

Base Route Prefix: `/api/v1`

## Endpoints Summary

### 1. Auth (`/api/v1/auth`)
- `POST /auth/login` - Authenticate user and issue JWT
- `POST /auth/refresh` - Refresh access token
- `GET /auth/me` - Current user profile
- `POST /auth/logout` - Invalidate session

### 2. Tenants (`/api/v1/tenants`)
- `GET /tenants` - List tenants / organizations
- `POST /tenants` - Create new tenant
- `GET /tenants/{tenant_id}` - Get tenant details
- `PUT /tenants/{tenant_id}` - Update tenant settings

### 3. People (`/api/v1/people`)
- `GET /people` - List professionals
- `POST /people` - Intake / create professional
- `POST /people/bulk-import` - Bulk import professionals
- `GET /people/{person_id}` - Get professional profile
- `PUT /people/{person_id}` - Update professional details

### 4. Onboarding (`/api/v1/onboarding`)
- `GET /onboarding/templates` - List onboarding templates
- `POST /onboarding/templates` - Create onboarding template
- `POST /onboarding/runs` - Start onboarding run
- `GET /onboarding/runs/{run_id}` - Get run progress and checklist items
- `PATCH /onboarding/runs/{run_id}/items/{item_id}` - Update checklist item status

### 5. Assignments (`/api/v1/assignments`)
- `GET /assignments/projects` - List projects
- `POST /assignments/projects` - Create project
- `GET /assignments/capacity` - Query capacity allocations
- `POST /assignments/allocate` - Assign professional to project

### 6. Access (`/api/v1/access`)
- `GET /access/requests` - List access requests
- `POST /access/requests` - Submit new access request
- `POST /access/requests/{request_id}/approve` - Approve request
- `POST /access/requests/{request_id}/provision` - Trigger provider provisioning
- `GET /access/requests/{request_id}/status` - Check provisioning state

### 7. Audit (`/api/v1/audit`)
- `GET /audit/logs` - Query activity timeline and audit logs
- `GET /audit/export` - Export audit events

### 8. Integrations (`/api/v1/integrations`)
- `GET /integrations/providers` - List connected services
- `POST /integrations/providers/{provider_id}/connect` - Connect service (OAuth/Token)
- `POST /integrations/webhooks/{provider_id}` - Webhook receiver endpoint
