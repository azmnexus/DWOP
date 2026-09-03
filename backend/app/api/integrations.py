from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter(prefix="/integrations", tags=["Integrations Layer"])


class ConnectProviderRequest(BaseModel):
    auth_code: str
    metadata: Dict[str, Any] = {}


@router.get("/providers")
async def list_connected_providers():
    """List connected third-party services (GitHub, Trello, Slack)."""
    return [
        {"provider": "github", "status": "connected"},
        {"provider": "slack", "status": "connected"},
        {"provider": "trello", "status": "disconnected"},
    ]


@router.post("/providers/{provider_id}/connect")
async def connect_provider(provider_id: str, payload: ConnectProviderRequest):
    """Initiate connection or exchange OAuth token for a provider."""
    return {"provider": provider_id, "status": "connected"}


@router.post("/webhooks/{provider_id}")
async def handle_provider_webhook(provider_id: str, request: Request):
    """Webhook receiver endpoint for external provider events."""
    payload = await request.json()
    return {"received": True, "provider": provider_id}
