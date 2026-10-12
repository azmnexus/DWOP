"""DWOP Centralized Dependency Injection Provider Hub (Task P-08).

Declares strongly-typed factory providers for database sessions, settings,
repositories, domain services, composite facades, and security guards per
CTO Mandate §3.8 and approved rulings D-1 through D-5.
"""

from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.dependencies import (
    get_current_active_user,
    get_current_policy_subject,
    get_current_user,
    require_admin,
    require_admin_or_manager,
    require_permissions,
    require_roles,
    enforce_scope_boundary,
    enforce_tenant_boundary,
)
from app.core.policy import Permission, PolicyEngine, PolicySubject, Scope, policy_engine
from app.facades.workforce import WorkforceOnboardingFacade
from app.models.user import User
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


# ---------------------------------------------------------------------------
# Database Session Lifecycle Provider
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped database session with guaranteed closure on teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Repository Providers (Approved Hybrid DI, Ruling D-2)
# ---------------------------------------------------------------------------
def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """Dependency provider for UserRepository."""
    return UserRepository(db)


def get_professional_repository(db: Session = Depends(get_db)) -> ProfessionalRepository:
    """Dependency provider for ProfessionalRepository."""
    return ProfessionalRepository(db)


def get_organization_repository(db: Session = Depends(get_db)) -> OrganizationRepository:
    """Dependency provider for OrganizationRepository."""
    return OrganizationRepository(db)


def get_project_repository(db: Session = Depends(get_db)) -> ProjectRepository:
    """Dependency provider for ProjectRepository."""
    return ProjectRepository(db)


def get_onboarding_repository(db: Session = Depends(get_db)) -> OnboardingRepository:
    """Dependency provider for OnboardingRepository."""
    return OnboardingRepository(db)


def get_assignment_repository(db: Session = Depends(get_db)) -> AssignmentRepository:
    """Dependency provider for AssignmentRepository."""
    return AssignmentRepository(db)


def get_access_repository(db: Session = Depends(get_db)) -> AccessRepository:
    """Dependency provider for AccessRepository."""
    return AccessRepository(db)


def get_audit_repository(db: Session = Depends(get_db)) -> AuditRepository:
    """Dependency provider for AuditRepository."""
    return AuditRepository(db)


# ---------------------------------------------------------------------------
# Domain Service Providers
# ---------------------------------------------------------------------------
def get_people_service(
    db: Session = Depends(get_db),
    repo: ProfessionalRepository = Depends(get_professional_repository),
) -> PeopleService:
    """Dependency provider for PeopleService with constructor-injected repository."""
    return PeopleService(db, repo=repo)


def get_onboarding_service(
    db: Session = Depends(get_db),
    repo: OnboardingRepository = Depends(get_onboarding_repository),
    professional_repo: ProfessionalRepository = Depends(get_professional_repository),
) -> OnboardingService:
    """Dependency provider for OnboardingService with constructor-injected repositories."""
    return OnboardingService(db, repo=repo, professional_repo=professional_repo)


def get_organization_service(
    db: Session = Depends(get_db),
    repo: OrganizationRepository = Depends(get_organization_repository),
) -> OrganizationService:
    """Documented Extension (Ruling D-1): Dependency provider for OrganizationService."""
    return OrganizationService(db, repo=repo)


def get_assignment_service(
    db: Session = Depends(get_db),
    assignment_repo: AssignmentRepository = Depends(get_assignment_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
    professional_repo: ProfessionalRepository = Depends(get_professional_repository),
    org_repo: OrganizationRepository = Depends(get_organization_repository),
) -> AssignmentService:
    """Dependency provider for AssignmentService with cross-domain repositories."""
    return AssignmentService(
        db,
        assignment_repo=assignment_repo,
        project_repo=project_repo,
        professional_repo=professional_repo,
        org_repo=org_repo,
    )


def get_access_service(
    db: Session = Depends(get_db),
    repo: AccessRepository = Depends(get_access_repository),
    professional_repo: ProfessionalRepository = Depends(get_professional_repository),
    onboarding_repo: OnboardingRepository = Depends(get_onboarding_repository),
) -> AccessService:
    """Dependency provider for AccessService with constructor-injected repositories."""
    return AccessService(
        db,
        repo=repo,
        professional_repo=professional_repo,
        onboarding_repo=onboarding_repo,
    )


def get_audit_service(
    db: Session = Depends(get_db),
    repo: AuditRepository = Depends(get_audit_repository),
) -> AuditService:
    """Documented Extension (Ruling D-1): Dependency provider for AuditService."""
    return AuditService(db, repo=repo)


# ---------------------------------------------------------------------------
# Composite Facade Provider
# ---------------------------------------------------------------------------
def get_intake_facade(db: Session = Depends(get_db)) -> WorkforceOnboardingFacade:
    """Dependency provider for WorkforceOnboardingFacade."""
    return WorkforceOnboardingFacade(db)


# ---------------------------------------------------------------------------
# Exported Public Symbols
# ---------------------------------------------------------------------------
__all__ = [
    # Infrastructure & Settings
    "get_db",
    "get_settings",
    "Settings",
    # Auth & Security
    "get_current_user",
    "get_current_active_user",
    "get_current_policy_subject",
    "require_admin",
    "require_admin_or_manager",
    "require_permissions",
    "require_roles",
    "enforce_scope_boundary",
    "enforce_tenant_boundary",
    "PolicySubject",
    "Permission",
    "Scope",
    "policy_engine",
    "User",
    # Repositories
    "get_user_repository",
    "get_professional_repository",
    "get_organization_repository",
    "get_project_repository",
    "get_onboarding_repository",
    "get_assignment_repository",
    "get_access_repository",
    "get_audit_repository",
    # Domain Services
    "get_people_service",
    "get_onboarding_service",
    "get_organization_service",
    "get_assignment_service",
    "get_access_service",
    "get_audit_service",
    # Facade
    "get_intake_facade",
]
