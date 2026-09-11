# DWOP Work Management Backend Implementation Contract

## Purpose

This specification converts the interactive Assignment Board prototype into a persistent, tenant-safe work-management service. It keeps DWOP centered on workforce readiness, capacity, governed assignment, and auditable delivery rather than cloning Trello.

## Domain model

### Board

A board is the operational workspace for one existing `Project`. Use a one-to-one relationship: `boards.project_id` must be unique. Fields: `id`, `tenant_id`, `project_id`, `name`, `description`, `status` (`active`, `archived`), `created_by`, `created_at`, `updated_at`, `version`.

### BoardMember

Fields: `id`, `tenant_id`, `board_id`, `professional_id`, `role` (`owner`, `manager`, `contributor`, `viewer`), `capacity_percentage`, `joined_at`, `added_by`. Enforce uniqueness on `(board_id, professional_id)` and capacity from 0–100.

### WorkflowColumn

Fields: `id`, `tenant_id`, `board_id`, `name`, `key`, `position`, `category` (`not_started`, `active`, `blocked`, `review`, `done`), `wip_limit`, `is_terminal`. Create the default columns atomically with a board: Backlog, Todo, In Progress, Blocked, In Review, Completed.

### Ticket

Fields: `id`, `tenant_id`, `board_id`, `column_id`, `ticket_number`, `title`, `description`, `priority` (`low`, `medium`, `high`, `critical`), `assignee_id`, `reporter_user_id`, `due_date`, `position`, `blocked_reason`, `completed_at`, `version`, `created_at`, `updated_at`. Ticket numbers should be immutable and human-readable, for example `DWOP-CORE-17`.

### ChecklistItem, Comment and ActivityEvent

- Checklist item: `ticket_id`, `title`, `is_complete`, `position`, `completed_by`, `completed_at`.
- Comment: `ticket_id`, `author_user_id`, `body`, timestamps; use soft deletion if required.
- Activity event: append-only record with actor, tenant, board, optional ticket, event type, before/after metadata, timestamp and correlation ID.

## Authorization

- ADMIN: create/archive boards; manage all members, columns and tickets; override transitions.
- MANAGER: manage members and tickets only on boards they own/manage; review and reopen work.
- MEMBER: read boards where they are a member; update their assigned tickets; report/unreport blockers; submit for review.
- Tenant checks must be applied by the database query, not only by frontend visibility.
- A ticket assignee must be an active member of the same board.

## Lifecycle rules

1. Board creation links an existing project and creates default columns in one transaction.
2. Adding a member validates professional status and records intended project capacity.
3. Ticket creation requires title, priority and a valid board. Assignment is optional.
4. Moving to `blocked` requires `blocked_reason`.
5. Moving to `review` is allowed for assignee, manager or admin.
6. Only manager/admin may move `review` to `completed`; completion stores actor and timestamp.
7. Reopening a completed ticket clears `completed_at` and requires a reason.
8. Enforce WIP limits server-side and return HTTP 409 when exceeded.
9. All mutations emit an activity event in the same transaction.
10. Use optimistic concurrency (`version` or ETag) so simultaneous drag operations cannot silently overwrite each other.

## REST API

Base path: `/api/v1/work-management`.

| Method | Route | Purpose |
|---|---|---|
| POST | `/boards` | Create a board for a project |
| GET | `/boards` | List boards visible to current user |
| GET/PATCH | `/boards/{board_id}` | Read or update board metadata |
| POST | `/boards/{board_id}/archive` | Archive board without deleting history |
| GET/POST | `/boards/{board_id}/members` | List or add board members |
| PATCH/DELETE | `/boards/{board_id}/members/{member_id}` | Change role/capacity or remove member |
| GET/POST | `/boards/{board_id}/columns` | List or create workflow columns |
| PATCH | `/boards/{board_id}/columns/reorder` | Atomically reorder columns |
| GET/POST | `/boards/{board_id}/tickets` | Filter/list or create tickets |
| GET/PATCH | `/tickets/{ticket_id}` | Read or edit ticket fields |
| POST | `/tickets/{ticket_id}/move` | Validated column/position transition |
| POST | `/tickets/{ticket_id}/assign` | Assign or unassign a board member |
| GET/POST | `/tickets/{ticket_id}/comments` | Read or create comments |
| GET/POST | `/tickets/{ticket_id}/checklist` | Read or create checklist items |
| PATCH | `/checklist-items/{item_id}` | Complete, rename or reorder item |
| GET | `/boards/{board_id}/activity` | Paginated immutable audit feed |
| GET | `/boards/{board_id}/metrics` | Counts, cycle time, overdue, blocked and workload metrics |

## Key payloads

```json
POST /boards
{"project_id":"uuid","name":"Platform delivery","description":"Q4 execution"}

POST /boards/{board_id}/members
{"professional_id":"uuid","role":"contributor","capacity_percentage":40}

POST /boards/{board_id}/tickets
{"title":"Implement SSO callback","description":"...","priority":"high","assignee_id":"uuid-or-null","due_date":"2026-10-01"}

POST /tickets/{ticket_id}/move
{"column_id":"uuid","position":2,"version":4,"reason":"optional except governed transitions"}
```

Return canonical resource objects after mutations. Validation errors should follow the existing safe API error format. Use 403 for scope/RBAC failures, 404 for tenant-safe not-found responses, 409 for version/WIP conflicts, and 422 for invalid payloads.

## List behavior

Ticket listing must support `column_id`, `assignee_id`, `priority`, `overdue`, `search`, `limit`, `cursor`, and stable ordering. Prefer cursor pagination. Board responses may include column ticket counts, but ticket bodies should be paginated independently.

## Capacity integration

Board membership must not silently replace formal assignment records. Adding a member should either create an actual project assignment through the assignment service or require an existing assignment. Capacity totals must be computed from persisted assignments and reject allocations above policy thresholds unless an ADMIN provides an audited override reason.

## Realtime and drag/drop

The initial version may refetch after each mutation. Later, publish board events by WebSocket or SSE. A move request must be atomic: validate RBAC, tenant, destination, WIP, and version; update positions; write audit event; commit; then broadcast.

## Database and delivery requirements

- UUID primary keys and indexed `tenant_id` on every table.
- Composite indexes for `(board_id, column_id, position)`, `(board_id, assignee_id)`, and `(tenant_id, due_date)`.
- Foreign keys should restrict destructive deletion; archive business records instead.
- Alembic migration, models, schemas, services, routes and automated tests are required.
- Seed only deterministic development examples; never seed production tenants.
- OpenAPI schemas must be authoritative so frontend TypeScript can match them.

## Acceptance tests

1. Admin creates a board linked to an existing project and six default columns appear.
2. Admin adds a professional; duplicate membership returns 409.
3. Admin creates and assigns a ticket; a non-member assignee is rejected.
4. Member can move their ticket to In Progress, Blocked with a reason, and In Review.
5. Member cannot complete their own reviewed ticket; manager/admin can.
6. Cross-tenant board, ticket and member identifiers return tenant-safe 404 responses.
7. Concurrent moves with a stale version return 409.
8. Every mutation produces one immutable activity event.
9. Capacity totals reflect actual persisted assignments after membership/allocation.
10. Board list, ticket filters and activity endpoints are paginated and stable.

## Frontend integration note

The current `WorkBoardPrototype` deliberately keeps members and tickets in React memory and labels them “session only.” Replace those state mutations with the endpoints above, hydrate the board on load, show mutation errors inline, and refetch or reconcile canonical server responses. Do not retain browser storage as a production data source.
