import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_admin
from app.models.user import User
from app.models.access import Integration, IntegrationProvider, IntegrationAuthType
from app.services.audit import AuditService

router = APIRouter(prefix="/integrations", tags=["Integrations Layer"])


class ConnectProviderRequest(BaseModel):
    auth_code: Optional[str] = None
    auth_type: Optional[str] = "oauth2"
    scopes: List[str] = []
    metadata: Dict[str, Any] = {}


class IntegrationRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    provider: str
    auth_type: str
    connection_status: str
    health_status: Optional[str] = None
    scopes: Optional[List[str]] = []
    updated_at: Optional[datetime] = None


@router.get("/providers", response_model=List[IntegrationRead])
def list_connected_providers(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List connected third-party integration providers configured for current tenant."""
    integrations = (
        db.query(Integration)
        .filter(Integration.tenant_id == current_user.tenant_id)
        .all()
    )
    results = []
    for it in integrations:
        results.append(
            IntegrationRead(
                id=it.id,
                tenant_id=it.tenant_id,
                provider=it.provider.value if hasattr(it.provider, "value") else str(it.provider),
                auth_type=it.auth_type.value if hasattr(it.auth_type, "value") else str(it.auth_type),
                connection_status=it.connection_status.value if hasattr(it.connection_status, "value") else str(it.connection_status),
                health_status=it.health_status,
                scopes=it.scopes if isinstance(it.scopes, list) else [],
                updated_at=it.updated_at,
            )
        )
    return results


@router.post("/providers/{provider_id}/connect", response_model=IntegrationRead)
def connect_provider(
    provider_id: str,
    payload: ConnectProviderRequest,
    operator: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Initiate or update a third-party service provider connection in current tenant (Requires ADMIN role)."""
    # Normalize provider enum
    provider_key = provider_id.lower().replace("-", "_")
    valid_providers = [p.value for p in IntegrationProvider]
    if provider_key not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider '{provider_id}'. Supported: {valid_providers}",
        )

    integration = (
        db.query(Integration)
        .filter(
            Integration.tenant_id == operator.tenant_id,
            Integration.provider == provider_key,
        )
        .first()
    )
    if not integration:
        integration = Integration(
            tenant_id=operator.tenant_id,
            provider=provider_key,
            auth_type=payload.auth_type or "oauth2",
            connection_status="connected",
            health_status="healthy",
            scopes=payload.scopes or ["repo", "read:org"],
            credentials_encrypted={"auth_code": payload.auth_code or "mock_secret"},
            updated_at=datetime.now(timezone.utc),
        )
        db.add(integration)
    else:
        integration.connection_status = "connected"
        integration.health_status = "healthy"
        integration.scopes = payload.scopes or integration.scopes
        integration.updated_at = datetime.now(timezone.utc)

    db.flush()

    AuditService(db).log_event(
        tenant_id=operator.tenant_id,
        actor_user_id=operator.id,
        action="integration.connected",
        target_type="Integration",
        target_id=integration.id,
        metadata={"provider": provider_key, "health_status": "healthy"},
        commit=False,
    )

    db.commit()
    db.refresh(integration)

    return IntegrationRead(
        id=integration.id,
        tenant_id=integration.tenant_id,
        provider=integration.provider.value if hasattr(integration.provider, "value") else str(integration.provider),
        auth_type=integration.auth_type.value if hasattr(integration.auth_type, "value") else str(integration.auth_type),
        connection_status=integration.connection_status.value if hasattr(integration.connection_status, "value") else str(integration.connection_status),
        health_status=integration.health_status,
        scopes=integration.scopes if isinstance(integration.scopes, list) else [],
        updated_at=integration.updated_at,
    )


@router.post("/webhooks/{provider_id}")
async def handle_provider_webhook(
    provider_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Webhook receiver endpoint for external provider event payloads."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    provider_key = provider_id.lower().replace("-", "_")

    # Log webhook receipt to audit log if tenant can be derived from header/query
    tenant_header = request.headers.get("X-Tenant-ID")
    if tenant_header:
        try:
            tenant_uuid = uuid.UUID(tenant_header)
            AuditService(db).log_event(
                tenant_id=tenant_uuid,
                actor_user_id=None,
                action="integration.webhook_received",
                target_type="Integration",
                target_id=None,
                metadata={"provider": provider_key, "keys": list(payload.keys())},
                commit=True,
            )
        except Exception:
            pass

    return {"received": True, "provider": provider_id, "status": "processed"}
