import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.talent import (
    Professional,
    Engagement,
    ProfessionalStatus,
    AvailabilityStatus,
)
from app.repositories.professional import ProfessionalRepository
from app.schemas.talent import (
    ProfessionalCreate,
    ProfessionalUpdate,
)
from app.services.audit import AuditService


class PeopleService:
    """Domain service for workforce directory, intake, and talent records."""

    def __init__(self, db: Session, repo: Optional[ProfessionalRepository] = None):
        self.db = db
        self.repo = repo or ProfessionalRepository(db)

    def list_people(
        self,
        tenant_id: uuid.UUID,
        status_filter: Optional[ProfessionalStatus] = None,
        availability_filter: Optional[AvailabilityStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Professional]:
        """List all professionals scoped strictly to tenant with optional filters."""
        return self.repo.list_filtered(
            tenant_id=tenant_id,
            status_filter=status_filter,
            availability_filter=availability_filter,
            skip=skip,
            limit=limit,
        )

    def get_person_by_id(
        self, tenant_id: uuid.UUID, person_id: uuid.UUID
    ) -> Optional[Professional]:
        """Retrieve a single professional strictly scoped to the tenant."""
        return self.repo.get_by_id(tenant_id, person_id)

    def create_person(
        self,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: ProfessionalCreate,
    ) -> Professional:
        """Intake / register a single professional with optional engagement and atomic audit."""
        existing = self.repo.get_by_email(tenant_id, payload.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Professional with email '{payload.email}' already exists in this tenant.",
            )

        professional = Professional(
            tenant_id=tenant_id,
            user_id=payload.user_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            status=payload.status,
            availability_status=payload.availability_status,
            skills=payload.skills,
        )
        self.repo.create(tenant_id, professional)

        if payload.engagement:
            engagement = Engagement(
                tenant_id=tenant_id,
                professional_id=professional.id,
                engagement_type=payload.engagement.engagement_type,
                start_date=payload.engagement.start_date,
                end_date=payload.engagement.end_date,
                contract_status=payload.engagement.contract_status,
                compensation_rate=payload.engagement.compensation_rate,
            )
            self.repo.create_engagement(engagement)

        # Log immutable audit event for candidate intake inside the transaction
        AuditService(self.db).log_event(
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            action="professional.created",
            target_type="Professional",
            target_id=professional.id,
            metadata={"email": professional.email, "status": professional.status.value},
            commit=False,
        )

        self.db.commit()
        self.db.refresh(professional)
        return professional

    def bulk_import_people(
        self,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: List[ProfessionalCreate],
    ) -> List[Professional]:
        """Bulk import an array of professionals in a single atomic database transaction."""
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payload array cannot be empty.",
            )

        created_records = []
        try:
            for item in payload:
                existing = self.repo.get_by_email(tenant_id, item.email)
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Duplicate detected: Professional with email '{item.email}' already exists.",
                    )

                prof = Professional(
                    tenant_id=tenant_id,
                    user_id=item.user_id,
                    first_name=item.first_name,
                    last_name=item.last_name,
                    email=item.email,
                    phone=item.phone,
                    status=item.status,
                    availability_status=item.availability_status,
                    skills=item.skills,
                )
                self.repo.create(tenant_id, prof)

                if item.engagement:
                    eng = Engagement(
                        tenant_id=tenant_id,
                        professional_id=prof.id,
                        engagement_type=item.engagement.engagement_type,
                        start_date=item.engagement.start_date,
                        end_date=item.engagement.end_date,
                        contract_status=item.engagement.contract_status,
                        compensation_rate=item.engagement.compensation_rate,
                    )
                    self.repo.create_engagement(eng)

                created_records.append(prof)

            # Log immutable audit event for atomic cohort bulk import
            if created_records:
                AuditService(self.db).log_event(
                    tenant_id=tenant_id,
                    actor_user_id=actor_id,
                    action="professional.bulk_imported",
                    target_type="Professional",
                    target_id=created_records[0].id,
                    metadata={
                        "count": len(created_records),
                        "cohort_emails": [p.email for p in created_records],
                    },
                    commit=False,
                )

            self.db.commit()
            for record in created_records:
                self.db.refresh(record)
            return created_records

        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to execute bulk import transaction: {str(e)}",
            )

    def update_person_profile(
        self,
        tenant_id: uuid.UUID,
        person_id: uuid.UUID,
        payload: ProfessionalUpdate,
    ) -> Professional:
        """Update professional details or status strictly scoped to tenant."""
        person = self.repo.update(tenant_id, person_id, payload)
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Professional '{person_id}' not found in current tenant.",
            )

        self.db.commit()
        self.db.refresh(person)
        return person
