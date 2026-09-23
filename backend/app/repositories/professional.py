"""Professional repository for talent directory, intake cohorts, and engagements."""
from __future__ import annotations

import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.talent import (
    AvailabilityStatus,
    Engagement,
    Professional,
    ProfessionalStatus,
)
from app.repositories.base import BaseRepository


class ProfessionalRepository(BaseRepository[Professional]):
    """Domain repository for Professional workforce subjects and contractual engagements."""

    def __init__(self, db: Session):
        super().__init__(db, Professional)

    def get_by_email(self, tenant_id: uuid.UUID, email: str) -> Optional[Professional]:
        """Fetch professional by email strictly scoped to tenant."""
        return (
            self._scoped_query(tenant_id)
            .filter(Professional.email == email.strip().lower())
            .first()
        )

    def get_by_user_id(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[Professional]:
        """Fetch professional associated with a system User login identity."""
        return (
            self._scoped_query(tenant_id)
            .filter(Professional.user_id == user_id)
            .first()
        )

    def list_filtered(
        self,
        tenant_id: uuid.UUID,
        status_filter: Optional[ProfessionalStatus] = None,
        availability_filter: Optional[AvailabilityStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Professional]:
        """Retrieve paginated talent directory filtered by status and availability."""
        query = self._scoped_query(tenant_id)
        if status_filter:
            query = query.filter(Professional.status == status_filter)
        if availability_filter:
            query = query.filter(Professional.availability_status == availability_filter)
        return query.offset(skip).limit(limit).all()

    def get_all(self, tenant_id: uuid.UUID) -> List[Professional]:
        """Fetch all professionals in the tenant."""
        return self._scoped_query(tenant_id).all()

    def get_engagement(
        self, tenant_id: uuid.UUID, professional_id: uuid.UUID
    ) -> Optional[Engagement]:
        """Fetch contractual engagement details for a professional."""
        return (
            self.db.query(Engagement)
            .filter(
                Engagement.professional_id == professional_id,
                Engagement.tenant_id == tenant_id,
            )
            .first()
        )

    def create_engagement(self, engagement: Engagement) -> Engagement:
        """Stage engagement entity without committing."""
        self.db.add(engagement)
        self.db.flush()
        return engagement

    def bulk_create(
        self,
        professionals: List[Professional],
        engagements: List[Engagement],
    ) -> None:
        """Stage a batch of professionals and associated engagements. Flushes without committing."""
        self.db.add_all(professionals)
        self.db.flush()
        self.db.add_all(engagements)
        self.db.flush()
