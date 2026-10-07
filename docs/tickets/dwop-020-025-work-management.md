# DWOP Work Management — Engineering Work Packages
## Ticket Series: DWOP-020 through DWOP-025

> **Document Status:** DRAFTED — Awaiting Khalifa Technical Review → Pending Management Go-Ahead
>
> **Authored by:** Usman (O-05 delivery)
> **Cross-referenced against:** `docs/WORK_MANAGEMENT_BACKEND_HANDOFF.md` · `docs/erd.md`
> **Dependency:** This series is structurally dependent on Task O-04 (ERD Delta Draft — Entities 20–23 by Khalifa). Implementation **cannot begin** until O-04 schema definitions are ratified and Management Go-Ahead is issued.
>
> **Execution Hold:** These tickets are fully scoped and ready for immediate team assignment. They must not be activated in the sprint registry until formal management approval is received.

---

## Governance Gate & Dependency Chain

```
O-04 (Khalifa — ERD Delta: Entities 20-23)
   └─► DWOP-020 (Schema & Migration)
          └─► DWOP-021 (Board & Column Service)
                 └─► DWOP-022 (Ticket Lifecycle & State Machine APIs)  ← consumes O-03 TicketStateMachine
                        └─► DWOP-023 (Membership, Roles & Capacity Linkage)
                               └─► DWOP-024 (Frontend Wiring & Real-Time Sync)  [Lead: Usman]
                                      └─► DWOP-025 (Verification Test Suite & Tenant Isolation Harness)
```

> **Dependency note on O-04:** The `Board`, `BoardMember`, `WorkflowColumn`, `Ticket`, `ChecklistItem`, `Comment`, and `ActivityEvent` entities (ERD Entities 20–23, per the handoff spec) are not yet formally drafted in `docs/erd.md`. Khalifa must complete O-04 before Alembic migrations in DWOP-020 can be authored.

---

## DWOP-020 · Work Management Schema Models & Alembic Migration

| Field | Value |
|---|---|
| **ID** | DWOP-020 |
| **Title** | Work Management Schema Models & Alembic Migration |
| **Type** | Backend — Data Layer |
| **Estimated Effort** | 3–4 days |
| **Proposed Owner** | Khalifa |
| **Depends On** | O-04 (ERD Delta), existing `Project` model |
| **Blocks** | DWOP-021, DWOP-022, DWOP-023, DWOP-025 |

### Objective
Define all persistent SQLAlchemy ORM models and generate an Alembic migration to introduce the Work Management data layer into the existing DWOP schema without modifying any existing entity or breaking any existing migration.

### Scope — New Models Required

All models must reside in `backend/app/models/work_management.py`. Every model must carry `tenant_id` (UUID FK → `tenants.id`, `CASCADE`, indexed) as its first non-PK column.

| Model | Table Name | Key Fields |
|---|---|---|
| `Board` | `boards` | `id`, `tenant_id`, `project_id` (unique FK), `name`, `description`, `status` (active/archived), `created_by` FK, `created_at`, `updated_at`, `version` |
| `WorkflowColumn` | `workflow_columns` | `id`, `tenant_id`, `board_id` FK, `name`, `key`, `position`, `category`, `wip_limit`, `is_terminal` |
| `BoardMember` | `board_members` | `id`, `tenant_id`, `board_id` FK, `professional_id` FK, `role`, `capacity_percentage` (0–100), `joined_at`, `added_by` FK; unique on `(board_id, professional_id)` |
| `Ticket` | `tickets` | `id`, `tenant_id`, `board_id` FK, `column_id` FK, `ticket_number` (immutable), `title`, `description`, `priority`, `assignee_id` FK, `reporter_user_id` FK, `due_date`, `position`, `blocked_reason`, `completed_at`, `version`, `created_at`, `updated_at` |
| `ChecklistItem` | `checklist_items` | `id`, `ticket_id` FK, `tenant_id`, `title`, `is_complete`, `position`, `completed_by` FK, `completed_at` |
| `TicketComment` | `ticket_comments` | `id`, `tenant_id`, `ticket_id` FK, `author_user_id` FK, `body`, `is_deleted`, `created_at`, `updated_at` |
| `ActivityEvent` | `activity_events` | `id`, `tenant_id`, `board_id` FK, `ticket_id` FK (nullable), `actor_user_id` FK, `event_type`, `before_metadata` JSONB, `after_metadata` JSONB, `correlation_id`, `occurred_at`; append-only |

### Required Composite Indexes
- `(board_id, column_id, position)` on `tickets`
- `(board_id, assignee_id)` on `tickets`
- `(tenant_id, due_date)` on `tickets`
- `(board_id, position)` on `workflow_columns`

### Acceptance Criteria
- [ ] All 7 models exist in `backend/app/models/work_management.py` and are importable with no circular import errors.
- [ ] A single Alembic migration file creates all 7 tables with correct FK constraints and indexes.
- [ ] `alembic upgrade head` completes without error against a clean PostgreSQL database.
- [ ] `alembic downgrade -1` rolls back the migration completely.
- [ ] No existing table, column, or index in prior migrations is modified.
- [ ] `board_id + professional_id` uniqueness is enforced at the database level.
- [ ] `ActivityEvent` repository raises `NotImplementedError` on `update`/`delete`.
- [ ] All models are registered in `backend/app/models/__init__.py`.

---

## DWOP-021 · Board & Column Administration Service Layer

| Field | Value |
|---|---|
| **ID** | DWOP-021 |
| **Title** | Board & Column Administration Service Layer |
| **Type** | Backend — Service & API Layer |
| **Estimated Effort** | 3–4 days |
| **Proposed Owner** | Walid |
| **Depends On** | DWOP-020 |
| **Blocks** | DWOP-022, DWOP-023, DWOP-024 |

### Objective
Implement the service layer and REST API endpoints for creating, reading, updating, and archiving boards and their workflow columns. Board creation must be a single atomic transaction that seeds the six default columns.

### REST API Endpoints (Base: `/api/v1/work-management`)

| Method | Route | RBAC Guard | Description |
|---|---|---|---|
| `POST` | `/boards` | `require_admin` | Create a board for an existing project |
| `GET` | `/boards` | `get_current_active_user` | List boards visible to current user |
| `GET` | `/boards/{board_id}` | `get_current_active_user` | Read board metadata |
| `PATCH` | `/boards/{board_id}` | `require_admin_or_manager` | Update board name/description |
| `POST` | `/boards/{board_id}/archive` | `require_admin` | Archive board, preserve all history |
| `GET` | `/boards/{board_id}/columns` | `get_current_active_user` | List columns ordered by position |
| `POST` | `/boards/{board_id}/columns` | `require_admin` | Create a custom column |
| `PATCH` | `/boards/{board_id}/columns/reorder` | `require_admin_or_manager` | Atomically reorder columns |

### Default Columns Seeded on Board Creation

| Position | Name | Key | Category | `is_terminal` |
|---|---|---|---|---|
| 1 | Backlog | `backlog` | `not_started` | false |
| 2 | Todo | `todo` | `not_started` | false |
| 3 | In Progress | `in_progress` | `active` | false |
| 4 | Blocked | `blocked` | `blocked` | false |
| 5 | In Review | `review` | `review` | false |
| 6 | Completed | `completed` | `done` | true |

### Key Business Rules
- `boards.project_id` must be unique. Return `HTTP 409` if a board already exists for the given project.
- Board archive: `active → archived` only. All writes on archived boards return `HTTP 403`.
- Column reorder is atomic; partial lists return `HTTP 422`.
- Every board/column mutation emits an `ActivityEvent` in the same transaction.

### Acceptance Criteria
- [ ] `POST /boards` creates board + 6 default columns in one transaction.
- [ ] Duplicate `project_id` returns `HTTP 409`.
- [ ] `GET /boards` returns only the current tenant's boards.
- [ ] Cross-tenant `board_id` returns `HTTP 404`.
- [ ] Archive sets `status = archived` and emits `ActivityEvent` atomically.
- [ ] All writes on archived board return `HTTP 403`.
- [ ] `PATCH .../columns/reorder` with incomplete list returns `HTTP 422`.
- [ ] All service logic lives in `backend/app/services/work_management.py`; routers contain no business logic.

---

## DWOP-022 · Ticket Lifecycle, State Machine & Move Transition APIs

| Field | Value |
|---|---|
| **ID** | DWOP-022 |
| **Title** | Ticket Lifecycle, State Machine & Move Transition APIs |
| **Type** | Backend — Service & API Layer |
| **Estimated Effort** | 4–5 days |
| **Proposed Owner** | Walid |
| **Depends On** | DWOP-021, O-03 (`TicketStateMachine`) |
| **Blocks** | DWOP-023, DWOP-024, DWOP-025 |

### Objective
Implement full ticket CRUD and the governed column-move transition API, consuming the existing `TicketStateMachine` from `backend/app/core/state_machines.py` (Task O-03). All mutations must emit an `ActivityEvent` and respect WIP limits.

### State Machine Integration (O-03 Reference)
The `TicketStateMachine` (lines 370–418 of `state_machines.py`) defines:

```
backlog → todo
todo → {in_progress, blocked}         [blocked: requires blocked_reason guard]
in_progress → {blocked, review}       [blocked: requires blocked_reason guard]
blocked → {in_progress, todo}
review → {completed, in_progress}     [completed: requires ADMIN or MANAGER role guard]
completed → terminal
```

The `POST /tickets/{ticket_id}/move` endpoint **must** call `TicketStateMachine.validate_transition()` exclusively. No inline `if/else` status checks are permitted in the service or router layer.

### REST API Endpoints

| Method | Route | RBAC Guard | Description |
|---|---|---|---|
| `POST` | `/boards/{board_id}/tickets` | `get_current_active_user` | Create a ticket |
| `GET` | `/boards/{board_id}/tickets` | `get_current_active_user` | List/filter with cursor pagination |
| `GET` | `/tickets/{ticket_id}` | `get_current_active_user` | Read a single ticket |
| `PATCH` | `/tickets/{ticket_id}` | `get_current_active_user` | Edit ticket fields |
| `POST` | `/tickets/{ticket_id}/move` | `get_current_active_user` | Governed column/position transition |
| `POST` | `/tickets/{ticket_id}/assign` | `require_admin_or_manager` | Assign or unassign a board member |
| `GET/POST` | `/tickets/{ticket_id}/comments` | `get_current_active_user` | Read or post comments |
| `GET/POST` | `/tickets/{ticket_id}/checklist` | `get_current_active_user` | Read or add checklist items |
| `PATCH` | `/checklist-items/{item_id}` | `get_current_active_user` | Complete, rename, or reorder item |

### Move Payload
```json
POST /tickets/{ticket_id}/move
{ "column_id": "uuid", "position": 2, "version": 4, "reason": "required for governed transitions" }
```

### Key Business Rules
- **Optimistic Concurrency:** `ticket.version != payload.version` → `HTTP 409`.
- **WIP Limit:** Column at capacity → `HTTP 409`.
- **Blocked:** Requires non-empty `blocked_reason` (enforced by state machine guard).
- **Review → Completed:** Requires ADMIN or MANAGER (enforced by state machine guard, `context={"actor": current_user}`).
- **Assignee:** Must be a `BoardMember` on the same board.
- **Ticket number:** Immutable once set.
- Every move, edit, assignment, and comment emits one `ActivityEvent`.

### Ticket Listing Filters
`column_id`, `assignee_id`, `priority`, `overdue` (bool), `search` (title full-text), `limit`, `cursor` — cursor-based pagination only.

### Acceptance Criteria
- [ ] Move delegates entirely to `TicketStateMachine.validate_transition()` — no inline status conditionals in service/router.
- [ ] Stale `version` returns `HTTP 409`.
- [ ] WIP-limited column returns `HTTP 409`.
- [ ] `blocked` without `blocked_reason` returns `HTTP 400`.
- [ ] `review → completed` by MEMBER returns `HTTP 400`.
- [ ] `review → completed` by ADMIN/MANAGER sets `completed_at` and succeeds.
- [ ] Non-member assignee returns `HTTP 400`.
- [ ] `overdue=true` returns only non-completed tickets past `due_date`.
- [ ] Cross-tenant `ticket_id` returns `HTTP 404`.
- [ ] Every mutation produces exactly one `ActivityEvent` with before/after metadata.

---

## DWOP-023 · Board Membership, Role Permissions & Capacity Linkage

| Field | Value |
|---|---|
| **ID** | DWOP-023 |
| **Title** | Board Membership, Role Permissions & Capacity Linkage |
| **Type** | Backend — Service & API Layer |
| **Estimated Effort** | 3 days |
| **Proposed Owner** | Walid |
| **Depends On** | DWOP-021, DWOP-022, existing `AssignmentService` |
| **Blocks** | DWOP-024, DWOP-025 |

### Objective
Implement board membership management endpoints and enforce the connection between board-level roles, platform RBAC (ADR-002), and the existing capacity assignment system.

### REST API Endpoints

| Method | Route | RBAC Guard | Description |
|---|---|---|---|
| `GET` | `/boards/{board_id}/members` | `get_current_active_user` | List board members |
| `POST` | `/boards/{board_id}/members` | `require_admin_or_manager` | Add a professional as member |
| `PATCH` | `/boards/{board_id}/members/{member_id}` | `require_admin_or_manager` | Change role or capacity |
| `DELETE` | `/boards/{board_id}/members/{member_id}` | `require_admin` | Remove a member |
| `GET` | `/boards/{board_id}/metrics` | `get_current_active_user` | Board-wide counts, cycle time, capacity |
| `GET` | `/boards/{board_id}/activity` | `get_current_active_user` | Paginated immutable activity feed |

### Board Role → Platform RBAC Mapping

| Board Role | Permitted Actions |
|---|---|
| `owner` | All admin actions on this board |
| `manager` | Manage members and tickets on their boards; review/reopen |
| `contributor` | Create/update assigned tickets; report blockers; submit for review |
| `viewer` | Read-only on boards where they are a member |

Platform RBAC (ADMIN/MANAGER/MEMBER) is the authoritative gate. Board roles are additive.

### Capacity Linkage Rules
Per `WORK_MANAGEMENT_BACKEND_HANDOFF.md` (Section: Capacity Integration):
- Adding a board member **must** either create a formal `Assignment` via `AssignmentService.allocate_capacity()` OR require an existing `Assignment` for the professional on the board's project.
- If neither condition is met → `HTTP 400: "A formal project assignment is required before adding a member to this board."`
- `capacity_percentage` on `BoardMember` is an intention field only. Platform-wide capacity is sourced from `Assignment` records.
- Metrics endpoint includes `capacity_utilization_pct` from `AssignmentService.get_capacity_overview()`.

### Acceptance Criteria
- [ ] `POST .../members` without active `Assignment` returns `HTTP 400`.
- [ ] Duplicate `professional_id` returns `HTTP 409`.
- [ ] `DELETE .../members/{id}` by non-ADMIN returns `HTTP 403`.
- [ ] `GET .../members` for non-member MEMBER returns `HTTP 404`.
- [ ] Metrics response includes: `total_tickets`, `open_tickets`, `blocked_tickets`, `overdue_tickets`, `completed_tickets`, `average_cycle_time_days`, `capacity_utilization_pct`.
- [ ] Activity feed is cursor-paginated and ordered descending.
- [ ] Every membership mutation emits an `ActivityEvent`.
- [ ] Cross-tenant `board_id` returns `HTTP 404`.

---

## DWOP-024 · Frontend Board Persistence Wiring & Real-Time Sync

| Field | Value |
|---|---|
| **ID** | DWOP-024 |
| **Title** | Frontend Board Persistence Wiring & Real-Time Sync |
| **Type** | Frontend — Integration & UI |
| **Estimated Effort** | 4–5 days |
| **Designated Lead** | **Usman** |
| **Depends On** | DWOP-021, DWOP-022, DWOP-023 |
| **Blocks** | DWOP-025 |

### Objective
Replace the `WorkBoardPrototype` session-only state mutations with persistent API calls. The browser must never be used as a production data source for board state.

> Per `WORK_MANAGEMENT_BACKEND_HANDOFF.md` (Section: Frontend Integration Note): *"Replace those state mutations with the endpoints above, hydrate the board on load, show mutation errors inline, and refetch or reconcile canonical server responses. Do not retain browser storage as a production data source."*

### Scope

| Area | Action |
|---|---|
| **Board Hydration** | On load: `GET /boards` + `GET /boards/{id}/tickets` to populate state from server. |
| **Drag & Drop** | Replace React memory mutation with `POST /tickets/{id}/move` passing `version`. Handle `HTTP 409` with user-facing refresh prompt. |
| **Ticket CRUD** | Wire forms to `POST /boards/{id}/tickets` and `PATCH /tickets/{id}`. Surface `HTTP 422` errors inline. |
| **Member Management** | Wire to `POST`/`DELETE /boards/{id}/members`. |
| **Error Handling** | All `HTTP 403`, `404`, `409`, `422` responses must surface a visible inline error — not a silent no-op. |
| **Real-Time (Phase 1)** | Refetch after every successful mutation. No optimistic local state. |
| **Real-Time (Phase 2, stretch)** | WebSocket or SSE from `ActivityEvent` stream. |
| **TypeScript Types** | Generate from `/api/v1/openapi.json`. No manually maintained frontend type definitions. |

### Acceptance Criteria
- [ ] Browser refresh fully restores board state from server with no data loss.
- [ ] Drag to new column calls `POST .../move` and does not commit UI state until `HTTP 200`.
- [ ] Stale version conflict surfaces a modal prompting the user to refresh.
- [ ] WIP-limited column drag surfaces the server's `HTTP 409` message.
- [ ] No board state persists in `localStorage` or `sessionStorage`.
- [ ] TypeScript types are generated from OpenAPI — not manually written.
- [ ] All API calls include `Authorization: Bearer <token>` header from auth context.
- [ ] Tenant-scoped `HTTP 404` responses do not expose raw UUIDs to the user.

---

## DWOP-025 · Work Management Verification Test Suite & Tenant Isolation Harness

| Field | Value |
|---|---|
| **ID** | DWOP-025 |
| **Title** | Work Management Verification Test Suite & Tenant Isolation Harness |
| **Type** | Backend — QA & Security |
| **Estimated Effort** | 3–4 days |
| **Proposed Owner** | Usman |
| **Depends On** | DWOP-020 through DWOP-023 |
| **Blocks** | Production Deployment Gate |

### Objective
Deliver a complete automated test suite verifying correctness and a tenant isolation harness guaranteeing zero cross-tenant data leakage across all new endpoints.

### Functional Test Matrix (per WORK_MANAGEMENT_BACKEND_HANDOFF.md Acceptance Tests)

| # | Scenario | Expected Result |
|---|---|---|
| 1 | Admin creates board linked to existing project | Six default columns appear |
| 2 | Admin adds professional already in `board_members` | `HTTP 409` |
| 3 | Admin assigns ticket to non-member | `HTTP 400` |
| 4 | Member moves ticket: Todo → In Progress → Blocked (with reason) → In Review | All transitions succeed |
| 5 | Member attempts `review → completed` | `HTTP 400` (guard fires) |
| 6 | Manager performs `review → completed` | Succeeds; `completed_at` is set |
| 7 | Concurrent move with stale `version` | `HTTP 409` |
| 8 | Every mutation produces one `ActivityEvent` | Verified via direct DB query |
| 9 | Capacity reflects persisted `Assignment` records | `BoardMember.capacity_percentage` alone does not alter platform metric |
| 10 | Ticket listing filters with cursor pagination | Stable, correct subsets |

### Tenant Isolation Harness
Two seeded test tenants (`tenant_a`, `tenant_b`) with full board, column, member, and ticket data:

| Test | Assert |
|---|---|
| `GET /boards/{board_id_from_tenant_b}` as `tenant_a` user | `HTTP 404` |
| `GET /tickets/{ticket_id_from_tenant_b}` as `tenant_a` user | `HTTP 404` |
| `POST /tickets/{ticket_id_from_tenant_b}/move` as `tenant_a` user | `HTTP 404` |
| `POST /boards/{board_id_from_tenant_b}/members` as `tenant_a` admin | `HTTP 404` |
| `GET /boards/{board_id_from_tenant_b}/activity` as `tenant_a` user | `HTTP 404` |
| Direct DB query — all new tables filtered by `tenant_id` | Zero rows for other tenant |

### State Machine Regression Tests
All `TicketStateMachine` transitions must be unit tested in isolation (no HTTP layer, no DB). Full matrix: every valid transition, every invalid transition, every guard failure.

### Acceptance Criteria
- [ ] All 10 functional acceptance tests pass against a seeded PostgreSQL test DB.
- [ ] All tenant isolation tests pass with zero cross-tenant leakage.
- [ ] `TicketStateMachine` unit tests cover 100% of declared transitions and guards.
- [ ] Test suite runs in under 60 seconds in CI.
- [ ] No test uses `sqlite` dialect; all tests target PostgreSQL.
- [ ] All new service methods achieve ≥ 80% branch coverage.
- [ ] Harness is self-seeding and deterministic across runs.

---

## Governance & Submission

### Phase 4 Dependency Check — O-04 Status

> **BLOCKER:** Task O-04 (ERD Delta Draft — Entities 20–23 by Khalifa) has **not been completed**. The new `Board`, `BoardMember`, `WorkflowColumn`, `Ticket`, `ChecklistItem`, `Comment`, and `ActivityEvent` entities are not formally specified in `docs/erd.md`. DWOP-020 cannot be authored until Khalifa ratifies these definitions.
>
> **Recommended Action:** Khalifa should deliver `docs/erd-delta-entities-20-23.md` incorporating the domain model from `WORK_MANAGEMENT_BACKEND_HANDOFF.md` (Section: Domain Model) before DWOP-020 is assigned.

### Submitted For Technical Review

This document is submitted to **Khalifa** for formal technical review of:
1. Schema model completeness and FK integrity across all 7 new models.
2. REST API endpoint accuracy against the frontend integration requirements.
3. State machine integration correctness (O-03 consumption in DWOP-022).
4. Capacity linkage rules and alignment with existing `AssignmentService`.

### Execution Hold Notice

> These tickets are **fully scoped and ready for team assignment**. They must not be moved to `In Sprint` or activated in the sprint registry until a formal **"Management Go-Ahead"** is received. The O-04 dependency and management gate must both be resolved before sprint activation.
