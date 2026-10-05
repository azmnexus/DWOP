"""DWOP-018: Dependency Injection Pattern verification suite.

Verifies:
1. Centralized dependency provider resolution across database, settings, repositories,
   domain services, and composite facade in backend/app/api/deps.py.
2. Inversion of Control (IoC) mock substitution via FastAPI app.dependency_overrides.
3. Clean session lifecycle teardown without transaction bleeding or connection leaks.
4. Zero-drift integration verification across all 10 refactored API routers.
"""

from datetime import datetime, timezone
import os
import sys
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Add backend root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.api.deps import (
    get_access_repository,
    get_access_service,
    get_assignment_repository,
    get_assignment_service,
    get_audit_repository,
    get_audit_service,
    get_db,
    get_intake_facade,
    get_onboarding_repository,
    get_onboarding_service,
    get_organization_repository,
    get_organization_service,
    get_people_service,
    get_professional_repository,
    get_project_repository,
    get_settings,
    get_user_repository,
    Settings,
)
from app.core.config import Settings as CoreSettings
from app.core.database import SessionLocal
from app.facades.workforce import WorkforceOnboardingFacade
from app.models.talent import Professional, ProfessionalStatus, AvailabilityStatus
from app.models.user import User, UserRole
from app.repositories.access import AccessRepository
from app.repositories.assignment import AssignmentRepository
from app.repositories.audit import AuditRepository
from app.repositories.onboarding import OnboardingRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.professional import ProfessionalRepository
from app.repositories.project import ProjectRepository
from app.repositories.user import UserRepository
from app.services.access import AccessService
from app.services.assignment import AssignmentService
from app.services.audit import AuditService
from app.services.onboarding import OnboardingService
from app.services.organization import OrganizationService
from app.services.people import PeopleService


client = TestClient(app)


def test_provider_resolution() -> None:
    """Verify that all dependency providers in deps.py resolve to valid typed instances."""
    print("\n[STEP 1] Verifying Dependency Provider Resolution...")
    # Settings provider
    settings_instance = get_settings()
    assert isinstance(settings_instance, (Settings, CoreSettings))
    print("  [PASS] get_settings() resolved to Settings instance")

    # DB session provider
    db_gen = get_db()
    db_session = next(db_gen)
    assert isinstance(db_session, Session)
    print("  [PASS] get_db() yielded active Session instance")

    try:
        # Repository providers
        user_repo = get_user_repository(db_session)
        assert isinstance(user_repo, UserRepository)
        prof_repo = get_professional_repository(db_session)
        assert isinstance(prof_repo, ProfessionalRepository)
        org_repo = get_organization_repository(db_session)
        assert isinstance(org_repo, OrganizationRepository)
        proj_repo = get_project_repository(db_session)
        assert isinstance(proj_repo, ProjectRepository)
        onb_repo = get_onboarding_repository(db_session)
        assert isinstance(onb_repo, OnboardingRepository)
        asgn_repo = get_assignment_repository(db_session)
        assert isinstance(asgn_repo, AssignmentRepository)
        access_repo = get_access_repository(db_session)
        assert isinstance(access_repo, AccessRepository)
        audit_repo = get_audit_repository(db_session)
        assert isinstance(audit_repo, AuditRepository)
        print("  [PASS] All 8 Repository Providers resolved with correct types")

        # Service providers
        people_svc = get_people_service(db_session, prof_repo)
        assert isinstance(people_svc, PeopleService)
        onb_svc = get_onboarding_service(db_session, onb_repo, prof_repo)
        assert isinstance(onb_svc, OnboardingService)
        org_svc = get_organization_service(db_session, org_repo)
        assert isinstance(org_svc, OrganizationService)
        asgn_svc = get_assignment_service(db_session, asgn_repo, proj_repo, prof_repo, org_repo)
        assert isinstance(asgn_svc, AssignmentService)
        access_svc = get_access_service(db_session, access_repo, prof_repo, onb_repo)
        assert isinstance(access_svc, AccessService)
        audit_svc = get_audit_service(db_session, audit_repo)
        assert isinstance(audit_svc, AuditService)
        print("  [PASS] All 6 Domain Service Providers resolved with constructor injection")

        # Composite Facade provider
        facade = get_intake_facade(db_session)
        assert isinstance(facade, WorkforceOnboardingFacade)
        print("  [PASS] get_intake_facade() resolved to WorkforceOnboardingFacade")
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_mock_substitution_inversion_of_control() -> None:
    """Verify that FastAPI app.dependency_overrides intercepts route execution cleanly."""
    print("\n[STEP 2] Verifying IoC Mock Substitution via app.dependency_overrides...")

    # Authenticate to get valid Bearer token
    login_resp = client.post("/api/v1/auth/login", json={"email": "admin@azm-nexus.com", "password": "Admin123!"})
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Define a standalone Mock PeopleService that returns canary mock data without database access
    canary_id = uuid.uuid4()
    mock_professional = Professional(
        id=canary_id,
        tenant_id=uuid.UUID(login_resp.json()["tenant_id"]),
        first_name="Canary",
        last_name="Injected",
        email="canary.injected@azm-nexus.com",
        phone="+234 800 000 0000",
        status=ProfessionalStatus.intake,
        availability_status=AvailabilityStatus.available,
        skills=["DependencyInjection", "IoC", "Mocking"],
        created_at=datetime.now(timezone.utc),
    )

    class MockPeopleService:
        def list_people(self, *args: Any, **kwargs: Any) -> List[Professional]:
            return [mock_professional]

    # Register dependency override for PeopleService
    app.dependency_overrides[get_people_service] = lambda: MockPeopleService()

    try:
        response = client.get("/api/v1/people/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["email"] == "canary.injected@azm-nexus.com"
        assert data[0]["first_name"] == "Canary"
        assert "DependencyInjection" in data[0]["skills"]
        print("  [PASS] Endpoint consumed MockPeopleService without querying database")
    finally:
        # Clear override and verify normal behavior restored
        app.dependency_overrides.pop(get_people_service, None)

    normal_resp = client.get("/api/v1/people/", headers=headers)
    assert normal_resp.status_code == 200
    normal_data = normal_resp.json()
    assert not any(p["email"] == "canary.injected@azm-nexus.com" for p in normal_data)
    print("  [PASS] Dependency override cleared; original provider restored")


def test_session_lifecycle_teardown() -> None:
    """Verify that get_db generator reliably closes sessions post-execution."""
    print("\n[STEP 3] Verifying Session Lifecycle Teardown...")

    # 1. Normal yield/teardown path
    gen = get_db()
    session = next(gen)
    assert session.is_active is True

    close_called = False
    original_close = session.close

    def tracked_close():
        nonlocal close_called
        close_called = True
        original_close()

    session.close = tracked_close

    try:
        next(gen)
    except StopIteration:
        pass  # teardown block executed

    assert close_called is True, "session.close() was not invoked by get_db finally block"
    print("  [PASS] get_db generator invoked session.close() in finally block")

    # 2. Exception yield/teardown path
    gen2 = get_db()
    session2 = next(gen2)
    close_called_on_err = False
    orig_close2 = session2.close

    def tracked_close2():
        nonlocal close_called_on_err
        close_called_on_err = True
        orig_close2()

    session2.close = tracked_close2

    try:
        gen2.throw(RuntimeError("Simulated request crash"))
    except RuntimeError:
        pass

    assert close_called_on_err is True, "session.close() was not called on exception"
    print("  [PASS] get_db generator reliably executed teardown on unhandled exception")


def test_universal_router_integration() -> None:
    """Verify zero-drift contract behavior across all 10 refactored API routers."""
    print("\n[STEP 4] Verifying Zero-Drift Across All 10 Refactored Routers...")

    # 1. Auth router
    login_resp = client.post("/api/v1/auth/login", json={"email": "admin@azm-nexus.com", "password": "Admin123!"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("  [PASS] 1. /api/v1/auth/login -> 200 (UserRepository + AuditService injected)")

    # 2. People router
    r = client.get("/api/v1/people/", headers=headers)
    assert r.status_code == 200
    print(f"  [PASS] 2. /api/v1/people/ -> 200 (PeopleService injected, {len(r.json())} records)")

    # 3. Onboarding router
    r = client.get("/api/v1/onboarding/templates", headers=headers)
    assert r.status_code == 200
    print(f"  [PASS] 3. /api/v1/onboarding/templates -> 200 (OnboardingService injected)")

    # 4. Departments router
    r = client.get("/api/v1/departments/", headers=headers)
    assert r.status_code == 200
    print(f"  [PASS] 4. /api/v1/departments/ -> 200 (OrganizationService injected)")

    # 5. Teams router
    r = client.get("/api/v1/teams/", headers=headers)
    assert r.status_code == 200
    print(f"  [PASS] 5. /api/v1/teams/ -> 200 (OrganizationService injected)")

    # 6. Clients router
    r = client.get("/api/v1/clients/", headers=headers)
    assert r.status_code == 200
    print(f"  [PASS] 6. /api/v1/clients/ -> 200 (ProjectRepository injected)")

    # 7. Assignments router
    r = client.get("/api/v1/assignments/capacity", headers=headers)
    assert r.status_code == 200
    r_asgn = client.get("/api/v1/assignments", headers=headers)
    assert r_asgn.status_code == 200
    print(f"  [PASS] 7. /api/v1/assignments -> 200 (AssignmentService + ProjectRepository injected)")

    # 8. Access router
    r = client.get("/api/v1/access/requests", headers=headers)
    assert r.status_code == 200
    print(f"  [PASS] 8. /api/v1/access/requests -> 200 (AccessService injected)")

    # 9. Audit router
    r = client.get("/api/v1/audit/logs", headers=headers)
    assert r.status_code == 200
    print(f"  [PASS] 9. /api/v1/audit/logs -> 200 (AuditService injected)")

    # 10. Integrations router
    r = client.get("/api/v1/integrations/providers", headers=headers)
    assert r.status_code == 200
    print(f"  [PASS] 10. /api/v1/integrations/providers -> 200 (AccessRepository injected)")


def main() -> None:
    print("=" * 80)
    print("DWOP-018: DEPENDENCY INJECTION PATTERN ARCHITECTURAL SUITE")
    print("=" * 80)
    test_provider_resolution()
    test_mock_substitution_inversion_of_control()
    test_session_lifecycle_teardown()
    test_universal_router_integration()
    print("=" * 80)
    print("DWOP-018 VERIFICATION PASSED (4/4 test suites green)")
    print("=" * 80)


if __name__ == "__main__":
    main()
