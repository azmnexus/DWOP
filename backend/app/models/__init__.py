"""SQLAlchemy Declarative Models (Khalifa's domain).
Models ordered to guarantee foreign key resolution:
TENANT -> USER -> PROFESSIONAL -> ENGAGEMENT -> DEPARTMENT -> TEAM -> CLIENT -> PROJECT -> ONBOARDING
"""
from app.core.database import Base
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.talent import (
    Professional,
    Engagement,
    ProfessionalStatus,
    AvailabilityStatus,
    EngagementType,
    ContractStatus,
)
from app.models.organization import Department, Team
from app.models.project import Client, Project, ClientStatus, ProjectStatus

from app.models.access import (
    Integration,
    IntegrationProvider,
    IntegrationAuthType,
    AccessRequest,
    AccessRequestStatus,
    AccessType,
    ApprovalDecision,
    ApprovalOutcome,
    AuditEvent,
)
from app.models.onboarding import (
    OnboardingTemplate,
    ChecklistTemplateItem,
    OnboardingRun,
    OnboardingItem,
)

__all__ = [
    "Base",
    "Tenant",
    "User",
    "UserRole",
    "Professional",
    "Engagement",
    "ProfessionalStatus",
    "AvailabilityStatus",
    "EngagementType",
    "ContractStatus",
    "Department",
    "Team",
    "Client",
    "ClientStatus",
    "Project",
    "ProjectStatus",
    "OnboardingTemplate",
    "ChecklistTemplateItem",
    "OnboardingRun",
    "OnboardingItem",
    "Integration",
    "IntegrationProvider",
    "IntegrationAuthType",
    "AccessRequest",
    "AccessRequestStatus",
    "AccessType",
    "ApprovalDecision",
    "ApprovalOutcome",
    "AuditEvent",
]
