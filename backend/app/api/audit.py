import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_audit_service, require_admin
from app.models.user import User
from app.schemas.audit import AuditEventRead
from app.services.audit import AuditService

router = APIRouter(prefix="/audit", tags=["Audit & Governance"])


@router.get("/logs", response_model=List[AuditEventRead])
def list_audit_logs(
    actor_user_id: Optional[uuid.UUID] = Query(None, description="Filter by actor user ID"),
    action: Optional[str] = Query(None, description="Filter by action verb (e.g. auth.login_successful)"),
    target_type: Optional[str] = Query(None, description="Filter by target entity type (e.g. Professional)"),
    skip: int = Query(0, ge=0, description="Offset pagination"),
    limit: int = Query(50, ge=1, le=100, description="Number of events to retrieve"),
    admin_user: User = Depends(require_admin),
    service: AuditService = Depends(get_audit_service),
):
    """Retrieve activity timeline and audit log events strictly scoped to current tenant.
    Requires ADMIN role. Ordered by timestamp descending.
    """
    return service.list_logs(
        tenant_id=admin_user.tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        skip=skip,
        limit=limit,
    )


@router.get("/export")
def export_audit_logs(
    admin_user: User = Depends(require_admin),
    service: AuditService = Depends(get_audit_service),
):
    """Export compliance audit logs for the current tenant."""
    events = service.list_logs(
        tenant_id=admin_user.tenant_id,
        limit=1000,
    )
    return {
        "status": "export_ready",
        "tenant_id": str(admin_user.tenant_id),
        "total_events": len(events),
        "events": [AuditEventRead.model_validate(e) for e in events],
    }
