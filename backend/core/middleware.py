"""
JWT Tenant Middleware (optional alternative to dependency injection).

Extracts tenant_id from Authorization header and populates ContextVar
before the request reaches the router. This ensures even non-auth endpoints
that manually verify can rely on tenancy, and logging can include tenant.

If no token present, ContextVar remains None; protected endpoints will 401/400.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.core.security import decode_access_token
from backend.core.tenancy import clear_tenant_id, set_current_user_claims, set_tenant_id


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Always clear first (prevent leakage from previous request in pooled context)
        clear_tenant_id()
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            try:
                payload = decode_access_token(token)
                tenant_id = payload.get("tenant_id") or payload.get("tid")
                if tenant_id:
                    set_tenant_id(tenant_id)
                    set_current_user_claims(payload)
            except Exception:
                # Don't block - let dependencies return 401; just ensure no stale context
                pass
        try:
            response = await call_next(request)
            return response
        finally:
            # Cleanup to avoid context leakage in async pool
            clear_tenant_id()
