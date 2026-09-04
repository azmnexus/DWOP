"""DWOP-010 database-backed access lifecycle verification."""
import asyncio
import os
import sys
import uuid
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import Base
from app.integrations.base import BaseProviderAdapter
import app.models  # noqa: F401 -- register all model tables
from app.models.access import (
    AccessRequestStatus,
    AccessType,
    AuditEvent,
    Integration,
    IntegrationAuthType,
    IntegrationProvider,
)
from app.models.talent import Professional
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.access import AccessLifecycleError, AccessService


class RaisingAdapter(BaseProviderAdapter):
    async def provision_access(self, user_email: str, role_or_scope: str):
        raise RuntimeError("simulated provider outage with internal details")

    async def revoke_access(self, user_email: str) -> bool:
        raise RuntimeError("simulated revoke outage")

    async def get_status(self):
        return {"status": "unavailable"}


async def main() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    tenant = Tenant(name="AZM Test", slug="azm-test")
    db.add(tenant)
    db.flush()
    admin = User(
        tenant_id=tenant.id,
        email="admin@example.test",
        hashed_password="not-used",
        role=UserRole.ADMIN,
    )
    member = User(
        tenant_id=tenant.id,
        email="member@example.test",
        hashed_password="not-used",
        role=UserRole.MEMBER,
    )
    db.add_all([admin, member])
    db.flush()
    professional = Professional(
        tenant_id=tenant.id,
        user_id=member.id,
        first_name="Demo",
        last_name="Engineer",
        email="engineer@example.test",
    )
    integration = Integration(
        tenant_id=tenant.id,
        provider=IntegrationProvider.github,
        auth_type=IntegrationAuthType.oauth2,
        credentials_encrypted={},
        scopes=["repo"],
    )
    db.add_all([professional, integration])
    db.commit()

    service = AccessService(db)
    request = service.create_request(
        tenant_id=tenant.id,
        professional_id=professional.id,
        integration_id=integration.id,
        access_type=AccessType.repository,
        role_or_scope="write",
        requested_by=member,
    )
    assert request.status == AccessRequestStatus.requested
    print("[PASS] Request persisted in requested state")

    member_visible = list(service.list_requests(member))
    assert [item.id for item in member_visible] == [request.id]
    print("[PASS] MEMBER listing is restricted to own professional profile")

    request = service.approve_request(
        tenant_id=tenant.id,
        request_id=request.id,
        approver=admin,
        rationale="Sprint 0 verification",
    )
    assert request.status == AccessRequestStatus.approved
    assert request.approved_by_user_id == admin.id
    print("[PASS] Approval persisted and attributed to approver")

    request, provider_result = await service.provision_request(
        tenant_id=tenant.id,
        request_id=request.id,
        actor=admin,
    )
    assert request.status == AccessRequestStatus.provisioned
    assert provider_result["provider"] == "github"
    print("[PASS] Approved request invokes adapter and becomes provisioned")

    try:
        service.approve_request(
            tenant_id=tenant.id,
            request_id=request.id,
            approver=admin,
        )
    except AccessLifecycleError:
        pass
    else:
        raise AssertionError("Invalid repeat approval should be blocked")
    print("[PASS] Invalid lifecycle transitions are blocked")

    request = await service.revoke_request(
        tenant_id=tenant.id,
        request_id=request.id,
        actor=admin,
    )
    assert request.status == AccessRequestStatus.revoked
    print("[PASS] Provisioned access can be revoked")

    events = db.query(AuditEvent).filter(AuditEvent.target_id == request.id).all()
    actions = [event.action for event in events]
    assert "access_request.created" in actions
    assert actions.count("access_request.status_changed") >= 4
    print("[PASS] Lifecycle changes are written to append-only audit events")

    foreign_tenant = Tenant(name="Other", slug="other")
    db.add(foreign_tenant)
    db.commit()
    try:
        service._request(foreign_tenant.id, request.id)
    except LookupError:
        pass
    else:
        raise AssertionError("Cross-tenant request lookup must fail")
    print("[PASS] Request lookup is tenant isolated")

    # Explicit failure path used again by DWOP-012.
    failing = Integration(
        tenant_id=tenant.id,
        provider=IntegrationProvider.github,
        auth_type=IntegrationAuthType.oauth2,
        credentials_encrypted={"simulate_failure": True},
        scopes=["repo"],
    )
    db.add(failing)
    db.commit()
    failed_request = service.create_request(
        tenant_id=tenant.id,
        professional_id=professional.id,
        integration_id=failing.id,
        access_type=AccessType.repository,
        role_or_scope="read",
        requested_by=member,
    )
    service.approve_request(
        tenant_id=tenant.id,
        request_id=failed_request.id,
        approver=admin,
    )
    failed_request, failed_result = await service.provision_request(
        tenant_id=tenant.id,
        request_id=failed_request.id,
        actor=admin,
    )
    assert failed_request.status == AccessRequestStatus.failed
    assert failed_result["error"]
    print("[PASS] Provider failure is persisted as failed without granting access")

    try:
        await service.provision_request(
            tenant_id=tenant.id,
            request_id=failed_request.id,
            actor=admin,
        )
    except AccessLifecycleError:
        pass
    else:
        raise AssertionError("Failed requests must not silently enter an undocumented retry transition")
    print("[PASS] Failed state is terminal until a retry policy is explicitly defined")

    exception_request = service.create_request(
        tenant_id=tenant.id,
        professional_id=professional.id,
        integration_id=integration.id,
        access_type=AccessType.repository,
        role_or_scope="read",
        requested_by=member,
    )
    service.approve_request(
        tenant_id=tenant.id, request_id=exception_request.id, approver=admin
    )
    with patch(
        "app.services.access.get_provider_adapter",
        return_value=RaisingAdapter(str(tenant.id), {}),
    ):
        exception_request, exception_result = await service.provision_request(
            tenant_id=tenant.id,
            request_id=exception_request.id,
            actor=admin,
        )
    assert exception_request.status == AccessRequestStatus.failed
    assert exception_result["error"] == "Provider provisioning failed."
    assert "internal details" not in exception_result["error"]
    print("[PASS] Unexpected provider exceptions fail safely and do not leak internals")

    print("DWOP-010 VERIFICATION PASSED")


if __name__ == "__main__":
    asyncio.run(main())
