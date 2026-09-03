import uuid
from contextvars import ContextVar
from typing import Optional
from fastapi import Request, Header, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

_tenant_context: ContextVar[Optional[uuid.UUID]] = ContextVar("tenant_id", default=None)


def get_current_tenant_id() -> Optional[uuid.UUID]:
    """Retrieve the current request's tenant UUID."""
    return _tenant_context.get()


def set_current_tenant_id(tenant_id: Optional[uuid.UUID]) -> None:
    """Set the tenant UUID in the current async context."""
    _tenant_context.set(tenant_id)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract Tenant ID from headers and store in context."""

    async def dispatch(self, request: Request, call_next):
        header_val = request.headers.get("X-Tenant-ID")
        if header_val:
            try:
                set_current_tenant_id(uuid.UUID(header_val))
            except ValueError:
                set_current_tenant_id(None)
        else:
            set_current_tenant_id(None)
        response = await call_next(request)
        return response


def get_required_tenant_id(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID")
) -> uuid.UUID:
    """FastAPI route dependency ensuring a valid tenant UUID is present."""
    tid = get_current_tenant_id()
    if not tid and x_tenant_id:
        try:
            tid = uuid.UUID(x_tenant_id)
            set_current_tenant_id(tid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid UUID format for X-Tenant-ID: {x_tenant_id}",
            )

    if not tid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required. Please provide the 'X-Tenant-ID' header.",
        )
    return tid
