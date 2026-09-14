import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.dependencies import RequireManager, get_current_user
from backend.models.user import User
from backend.schemas.notification import NotificationCreate, NotificationRead
from backend.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.post("", response_model=NotificationRead, status_code=201, dependencies=[Depends(RequireManager)])
async def create_notification(payload: NotificationCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = NotificationService(db)
    return await svc.create(payload.model_dump(), tenant_id=current.tenant_id)

@router.get("", response_model=list[NotificationRead])
async def list_notifications(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = NotificationService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id)
    return items

@router.get("/mine", response_model=list[NotificationRead])
async def my_notifications(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    """Return notifications for the authenticated user only."""
    from backend.models.notification import Notification
    svc = NotificationService(db)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id, filters=[Notification.recipient_user_id == current.id])
    return items

@router.get("/{notification_id}", response_model=NotificationRead)
async def get_notification(notification_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = NotificationService(db)
    return await svc.get(notification_id, tenant_id=current.tenant_id)

@router.post("/{notification_id}/mark-sent", response_model=NotificationRead, dependencies=[Depends(RequireManager)])
async def mark_sent(notification_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = NotificationService(db)
    return await svc.mark_sent(notification_id, tenant_id=current.tenant_id)
