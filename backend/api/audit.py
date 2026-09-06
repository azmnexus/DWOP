import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.audit import AuditEventCreate, AuditEventRead
from backend.services.audit import AuditService

router = APIRouter(prefix="/audit-events", tags=["audit"])

# NOTE: Append-only ledger - ONLY POST and GET are exposed.
# PUT, PATCH, DELETE are strictly forbidden at framework level (no routes registered)
# plus service-level 405 guards for defense-in-depth.


@router.post("", response_model=AuditEventRead, status_code=status.HTTP_201_CREATED)
async def create_audit_event(payload: AuditEventCreate, request: Request, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    """
    Log an audit event. Metadata is auto-enriched with IP and User-Agent for forensic integrity.
    Tamper-evident: no update/delete path exists.
    """
    svc = AuditService(db)
    enriched = dict(payload.metadata or {})
    # Forensic enrichment
    enriched.setdefault("ip", request.client.host if request.client else None)
    enriched.setdefault("user_agent", request.headers.get("user-agent"))
    enriched.setdefault("actor_email", current.email)
    event = await svc.log_event(
        action=payload.action,
        target_type=payload.target_type,
        target_id=payload.target_id,
        actor_user_id=current.id,
        metadata=enriched,
        tenant_id=current.tenant_id,
    )
    return event


@router.get("", response_model=list[AuditEventRead])
async def list_audit_events(
    target_type: str | None = Query(default=None, description="Filter by target_type e.g., AccessRequest"),
    target_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    svc = AuditService(db)
    filters = []
    from backend.models.audit import AuditEvent

    if target_type:
        filters.append(AuditEvent.target_type == target_type)
    if target_id:
        filters.append(AuditEvent.target_id == target_id)
    if action:
        filters.append(AuditEvent.action == action)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id, filters=filters)
    return items


@router.get("/{event_id}", response_model=AuditEventRead)
async def get_audit_event(event_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = AuditService(db)
    return await svc.get(event_id, tenant_id=current.tenant_id)
