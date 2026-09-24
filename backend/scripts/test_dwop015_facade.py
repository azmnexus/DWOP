"""DWOP-015 Workforce Onboarding Facade verification suite."""

import asyncio
import os
import sys
import uuid
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.models  # noqa: F401 -- register all model tables
from app.core.database import Base
from app.facades.workforce import ToolAccessSpec, WorkforceOnboardingFacade
from app.models.access import (
    AccessRequest,
    AccessType,
    Integration,
    IntegrationAuthType,
    IntegrationProvider,
)
from app.models.audit import AuditEvent
from app.models.onboarding import (
    ChecklistTemplateItem,
    OnboardingRun,
    OnboardingTemplate,
)
from app.models.talent import Professional
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.onboarding import OnboardingRunCreate
from app.schemas.talent import ProfessionalCreate
from app.services.access import AccessService
from app.services.onboarding import OnboardingService
from app.services.people import PeopleService


def candidate(email: str) -> ProfessionalCreate:
    return ProfessionalCreate(
        first_name="Facade",
        last_name="Candidate",
        email=email,
        skills=["Python", "SQLAlchemy"],
    )


def add_template(db, tenant_id: uuid.UUID, title: str) -> OnboardingTemplate:
    template = OnboardingTemplate(
        tenant_id=tenant_id,
        role_target="Engineer",
        title=title,
        version=1,
        is_active=True,
    )
    db.add(template)
    db.flush()
    db.add(
        ChecklistTemplateItem(
            template_id=template.id,
            title="Complete workforce setup",
            order_index=1,
            default_due_days=2,
        )
    )
    return template


def add_integration(
    db,
    tenant_id: uuid.UUID,
    provider: IntegrationProvider,
) -> Integration:
    integration = Integration(
        tenant_id=tenant_id,
        provider=provider,
        auth_type=IntegrationAuthType.oauth2,
        credentials_encrypted={},
        scopes=[],
    )
    db.add(integration)
    db.flush()
    return integration


async def main() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    tenant_a = Tenant(name="Facade Tenant A", slug="facade-tenant-a")
    tenant_b = Tenant(name="Facade Tenant B", slug="facade-tenant-b")
    db.add_all([tenant_a, tenant_b])
    db.flush()

    operator_a = User(
        tenant_id=tenant_a.id,
        email="facade-admin-a@example.com",
        hashed_password="not-used",
        role=UserRole.ADMIN,
    )
    operator_b = User(
        tenant_id=tenant_b.id,
        email="facade-admin-b@example.com",
        hashed_password="not-used",
        role=UserRole.ADMIN,
    )
    db.add_all([operator_a, operator_b])
    db.flush()

    template_a = add_template(db, tenant_a.id, "Tenant A Engineering")
    template_b = add_template(db, tenant_b.id, "Tenant B Engineering")
    github_a = add_integration(db, tenant_a.id, IntegrationProvider.github)
    slack_a = add_integration(db, tenant_a.id, IntegrationProvider.slack)
    github_b = add_integration(db, tenant_b.id, IntegrationProvider.github)
    db.commit()

    facade = WorkforceOnboardingFacade(db)

    success_email = "facade-success@example.com"
    professional, onboarding_run, access_requests = await facade.intake_and_enroll(
        tenant_id=tenant_a.id,
        operator=operator_a,
        candidate_data=candidate(success_email),
        template_id=template_a.id,
        tool_requests=[
            github_a.id,
            ToolAccessSpec(
                integration_id=str(slack_a.id),
                role_or_scope="contributor",
            ),
        ],
    )

    assert db.query(Professional).filter(Professional.id == professional.id).one()
    assert db.query(OnboardingRun).filter(OnboardingRun.id == onboarding_run.id).one()
    persisted_access = (
        db.query(AccessRequest)
        .filter(AccessRequest.professional_id == professional.id)
        .all()
    )
    assert len(persisted_access) == 2
    assert len(access_requests) == 2
    assert access_requests[0].access_type == AccessType.repository
    assert access_requests[0].role_or_scope == "member"
    assert access_requests[1].access_type == AccessType.channel
    assert access_requests[1].role_or_scope == "contributor"
    final_event = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.tenant_id == tenant_a.id,
            AuditEvent.action == "workforce.intake_enrolled",
            AuditEvent.target_id == professional.id,
        )
        .one()
    )
    assert final_event.actor_user_id == operator_a.id
    print("[PASS] Successful facade call persisted professional, run, access, and final audit")

    rollback_email = "facade-rollback@example.com"
    captured: dict[str, object] = {}
    access_call_count = 0
    original_create_person = PeopleService.create_person
    original_start_onboarding_run = OnboardingService.start_onboarding_run
    original_create_request = AccessService.create_request

    def capture_person(service, *args, **kwargs):
        created = original_create_person(service, *args, **kwargs)
        captured["professional_id"] = created.id
        return created

    def capture_onboarding_run(service, *args, **kwargs):
        created = original_start_onboarding_run(service, *args, **kwargs)
        captured["onboarding_run_id"] = created.id
        return created

    def fail_second_access_request(service, *args, **kwargs):
        nonlocal access_call_count
        access_call_count += 1
        if access_call_count == 2:
            raise RuntimeError("forced access-stage failure")
        created = original_create_request(service, *args, **kwargs)
        captured["access_request_id"] = created.id
        return created

    with (
        patch.object(PeopleService, "create_person", new=capture_person),
        patch.object(
            OnboardingService,
            "start_onboarding_run",
            new=capture_onboarding_run,
        ),
        patch.object(
            AccessService,
            "create_request",
            new=fail_second_access_request,
        ),
    ):
        try:
            await facade.intake_and_enroll(
                tenant_id=tenant_a.id,
                operator=operator_a,
                candidate_data=candidate(rollback_email),
                template_id=template_a.id,
                tool_requests=[github_a.id, slack_a.id],
            )
        except RuntimeError as exc:
            assert str(exc) == "forced access-stage failure"
        else:
            raise AssertionError("Forced access-stage failure was not re-raised")

    rolled_back_professional_id = captured["professional_id"]
    assert (
        db.query(Professional)
        .filter(Professional.id == rolled_back_professional_id)
        .first()
        is None
    )
    assert (
        db.query(OnboardingRun)
        .filter(OnboardingRun.professional_id == rolled_back_professional_id)
        .first()
        is None
    )
    assert (
        db.query(AccessRequest)
        .filter(AccessRequest.professional_id == rolled_back_professional_id)
        .first()
        is None
    )
    assert (
        db.query(AuditEvent)
        .filter(
            AuditEvent.action == "workforce.intake_enrolled",
            AuditEvent.target_id == rolled_back_professional_id,
        )
        .first()
        is None
    )
    assert (
        db.query(AccessRequest)
        .filter(AccessRequest.id == captured["access_request_id"])
        .first()
        is None
    )
    assert (
        db.query(AuditEvent)
        .filter(
            AuditEvent.action == "professional.created",
            AuditEvent.target_id == rolled_back_professional_id,
        )
        .first()
        is None
    )
    assert (
        db.query(AuditEvent)
        .filter(
            AuditEvent.action == "onboarding_run.created",
            AuditEvent.target_id == captured["onboarding_run_id"],
        )
        .first()
        is None
    )
    assert (
        db.query(AuditEvent)
        .filter(
            AuditEvent.action == "access_request.created",
            AuditEvent.target_id == captured["access_request_id"],
        )
        .first()
        is None
    )
    print("[PASS] Access-stage exception rolled back every facade-created record")

    foreign_template_email = "facade-foreign-template@example.com"
    try:
        await facade.intake_and_enroll(
            tenant_id=tenant_a.id,
            operator=operator_a,
            candidate_data=candidate(foreign_template_email),
            template_id=template_b.id,
        )
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Tenant A was allowed to use tenant B's template")
    assert (
        db.query(Professional)
        .filter(Professional.email == foreign_template_email)
        .first()
        is None
    )
    print("[PASS] Cross-tenant onboarding template use was rejected and rolled back")

    foreign_integration_email = "facade-foreign-integration@example.com"
    try:
        await facade.intake_and_enroll(
            tenant_id=tenant_a.id,
            operator=operator_a,
            candidate_data=candidate(foreign_integration_email),
            template_id=template_a.id,
            tool_requests=[str(github_b.id)],
        )
    except LookupError:
        pass
    else:
        raise AssertionError("Tenant A was allowed to use tenant B's integration")
    assert (
        db.query(Professional)
        .filter(Professional.email == foreign_integration_email)
        .first()
        is None
    )
    print("[PASS] Cross-tenant integration use was rejected and rolled back")

    default_email = "facade-default-commit@example.com"
    default_professional = PeopleService(db).create_person(
        tenant_id=tenant_a.id,
        actor_id=operator_a.id,
        payload=candidate(default_email),
    )
    default_professional_id = default_professional.id
    db.rollback()
    assert db.query(Professional).filter(Professional.id == default_professional_id).one()

    default_run = OnboardingService(db).start_onboarding_run(
        tenant_id=tenant_a.id,
        operator=operator_a,
        payload=OnboardingRunCreate(
            professional_id=default_professional_id,
            template_id=template_a.id,
        ),
    )
    default_run_id = default_run.id
    db.rollback()
    assert db.query(OnboardingRun).filter(OnboardingRun.id == default_run_id).one()

    default_request = AccessService(db).create_request(
        tenant_id=tenant_a.id,
        professional_id=default_professional_id,
        integration_id=github_a.id,
        access_type=AccessType.repository,
        role_or_scope="read",
        requested_by=operator_a,
    )
    default_request_id = default_request.id
    db.rollback()
    assert db.query(AccessRequest).filter(AccessRequest.id == default_request_id).one()
    print("[PASS] Default commit=True behavior remains compatible for all three services")

    db.close()
    print("DWOP-015 FACADE VERIFICATION PASSED")


if __name__ == "__main__":
    asyncio.run(main())
