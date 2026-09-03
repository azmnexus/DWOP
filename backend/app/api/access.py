from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/access", tags=["Access Request Lifecycle"])


class AccessRequestCreate(BaseModel):
    user_id: str
    provider: str  # github, trello, slack
    role_requested: str
    justification: Optional[str] = None


@router.get("/requests")
async def list_access_requests():
    """List access requests."""
    return [
        {
            "id": "req_01",
            "user_id": "usr_01",
            "provider": "github",
            "status": "pending_approval",
        }
    ]


@router.post("/requests")
async def create_access_request(payload: AccessRequestCreate):
    """Submit a new access request."""
    return {
        "id": "req_new",
        "provider": payload.provider,
        "status": "pending_approval",
    }


@router.post("/requests/{request_id}/approve")
async def approve_access_request(request_id: str):
    """Approve an access request."""
    return {"id": request_id, "status": "approved"}


@router.post("/requests/{request_id}/provision")
async def provision_access_request(request_id: str):
    """Trigger provider provisioning adapter."""
    return {"id": request_id, "status": "provisioning_triggered"}


@router.get("/requests/{request_id}/status")
async def get_provisioning_status(request_id: str):
    """Check provisioning state."""
    return {"id": request_id, "status": "active", "provider": "github"}
