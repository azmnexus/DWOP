import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_admin_or_manager
from app.models.user import User
from app.schemas.access import (
    AccessApprovalRequest,
    AccessProvisionResult,
    AccessRequestCreate,
    AccessRequestRead,
)
from app.services.access import AccessLifecycleError, AccessService

router = APIRouter(prefix="/access", tags=["Access Request Lifecycle"])


def _not_found_or_conflict(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/requests", response_model=list[AccessRequestRead])
def list_access_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List access requests scoped to the authenticated user's tenant."""
    return AccessService(db).list_requests(current_user)


@router.post(
    "/requests",
    response_model=AccessRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_access_request(
    payload: AccessRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Submit a tenant-scoped access request in ``requested`` state."""
    try:
        return AccessService(db).create_request(
            tenant_id=current_user.tenant_id,
            professional_id=payload.professional_id,
            integration_id=payload.integration_id,
            access_type=payload.access_type,
            role_or_scope=payload.role_or_scope,
            requested_by=current_user,
        )
    except (LookupError, AccessLifecycleError) as exc:
        raise _not_found_or_conflict(exc) from exc


@router.post("/requests/{request_id}/approve", response_model=AccessRequestRead)
def approve_access_request(
    request_id: uuid.UUID,
    payload: AccessApprovalRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager),
):
    """Approve a requested access request; ADMIN/MANAGER only."""
    try:
        return AccessService(db).approve_request(
            tenant_id=current_user.tenant_id,
            request_id=request_id,
            approver=current_user,
            rationale=payload.rationale if payload else None,
        )
    except (LookupError, AccessLifecycleError) as exc:
        raise _not_found_or_conflict(exc) from exc


@router.post("/requests/{request_id}/provision", response_model=AccessProvisionResult)
async def provision_access_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager),
):
    """Invoke the provider adapter for an approved access request."""
    try:
        request, result = await AccessService(db).provision_request(
            tenant_id=current_user.tenant_id,
            request_id=request_id,
            actor=current_user,
        )
        return AccessProvisionResult(
            request=request,
            provider=result.get("provider", "unknown"),
            provider_status=result.get("status", request.status.value),
            external_reference=result.get("external_reference"),
            error=result.get("error"),
        )
    except (LookupError, AccessLifecycleError, ValueError) as exc:
        raise _not_found_or_conflict(exc) from exc


@router.post("/requests/{request_id}/revoke", response_model=AccessRequestRead)
async def revoke_access_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager),
):
    """Revoke provider access while preserving an auditable request history."""
    try:
        return await AccessService(db).revoke_request(
            tenant_id=current_user.tenant_id,
            request_id=request_id,
            actor=current_user,
        )
    except (LookupError, AccessLifecycleError, ValueError) as exc:
        raise _not_found_or_conflict(exc) from exc


@router.get("/requests/{request_id}/status", response_model=AccessRequestRead)
def get_provisioning_status(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Read the persisted current state of one tenant-scoped access request."""
    try:
        return AccessService(db).get_request_for_user(current_user, request_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
