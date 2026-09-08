# ADR-001: Scaling DWOP from 10 to 1,000 Active Users

**Status**: Proposed
**Date**: 2026-09-07
**Authors**: Khalifa
**Deciders**: AZM Nexus Engineering Leadership

## Context

DWOP Sprint 0 demonstrates a synthetic cohort of 10 professionals. The commercial
roadmap targets 1,000 concurrent active users within the 61–90 day horizon.

## Current Architecture (Sprint 0 Baseline)

| Component | Current State | Capacity Ceiling |
|---|---|---|
| Database | Single PostgreSQL | ~500 concurrent connections |
| API | Single uvicorn process | ~200 req/s (single worker) |
| Auth | Stateless JWT | Unlimited |
| Multi-Tenancy | ContextVar scoping | Linear with tenants |
| Background Jobs | None | N/A |
| File Storage | URL string refs | No object storage |
| Caching | None | Every request hits DB |

## Upgrade Triggers

### Trigger 1: > 50 Concurrent API Users
**Decision**: Scale uvicorn workers to match CPU cores.
**Action**: `gunicorn -w $(nproc) -k uvicorn.workers.UvicornWorker`

### Trigger 2: > 200 Professionals per Tenant
**Decision**: Deploy PgBouncer for connection pooling.

### Trigger 3: > 500 Concurrent Users
**Decision**: Horizontal API replicas behind ALB/nginx. JWT is stateless.

### Trigger 4: > 1,000 Audit Events/Day
**Decision**: Partition `audit_events` by timestamp (monthly).

### Trigger 5: Provider Adapter Latency > 2s
**Decision**: Async task queue (Redis + ARQ/Celery). Idempotent adapter calls.

### Trigger 6: > 5 Tenants with Custom Branding
**Decision**: S3/GCS object storage + CDN.

### Trigger 7: Enterprise SSO Requirement
**Decision**: OIDC/SAML federation. JWT infrastructure already OIDC-compatible.

### Trigger 8: > 10,000 Professionals Rows
**Decision**: Cursor-based pagination + composite indexes.

## Decision Matrix

| Trigger | At 100 Users | At 1,000 Users | Effort |
|---|---|---|---|
| Multi-worker uvicorn | Now | Critical | Low |
| PgBouncer | Soon | Critical | Low |
| Horizontal scaling | Later | Required | Medium |
| Audit partitioning | Later | Recommended | Low |
| Task queue | Later | Required | High |
| Object storage | Later | Recommended | Low |
| Enterprise SSO | 60-day | Required | High |
| Cursor pagination | Later | Required | Low |
