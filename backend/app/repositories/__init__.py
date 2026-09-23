"""Domain repositories providing strictly typed, tenant-scoped data access."""
from app.repositories.base import BaseRepository
from app.repositories.user import UserRepository
from app.repositories.professional import ProfessionalRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.project import ProjectRepository
from app.repositories.onboarding import OnboardingRepository
from app.repositories.assignment import AssignmentRepository
from app.repositories.access import AccessRepository
from app.repositories.audit import AuditRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "ProfessionalRepository",
    "OrganizationRepository",
    "ProjectRepository",
    "OnboardingRepository",
    "AssignmentRepository",
    "AccessRepository",
    "AuditRepository",
]
