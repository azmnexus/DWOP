import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.dependencies import RequireManager, get_current_user
from backend.models.user import User
from backend.schemas.document_acknowledgement import DocumentAcknowledgementCreate, DocumentAcknowledgementRead
from backend.services.document_acknowledgement import DocumentAcknowledgementService

router = APIRouter(prefix="/document-acknowledgements", tags=["document-acknowledgements"])

@router.post("", response_model=DocumentAcknowledgementRead, status_code=201, dependencies=[Depends(RequireManager)])
async def create_acknowledgement(payload: DocumentAcknowledgementCreate, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = DocumentAcknowledgementService(db)
    return await svc.create(payload.model_dump(), tenant_id=current.tenant_id)

@router.get("", response_model=list[DocumentAcknowledgementRead])
async def list_acknowledgements(professional_id: uuid.UUID | None = Query(default=None), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = DocumentAcknowledgementService(db)
    filters = []
    if professional_id:
        from backend.models.document_acknowledgement import DocumentAcknowledgement
        filters.append(DocumentAcknowledgement.professional_id == professional_id)
    items, _ = await svc.list(page=page, page_size=page_size, tenant_id=current.tenant_id, filters=filters)
    return items

@router.get("/{ack_id}", response_model=DocumentAcknowledgementRead)
async def get_acknowledgement(ack_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = DocumentAcknowledgementService(db)
    return await svc.get(ack_id, tenant_id=current.tenant_id)

@router.post("/{ack_id}/acknowledge", response_model=DocumentAcknowledgementRead)
async def acknowledge_document(ack_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(get_current_user)):
    svc = DocumentAcknowledgementService(db)
    return await svc.acknowledge(ack_id, tenant_id=current.tenant_id)
