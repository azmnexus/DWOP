from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.access import (
    AccessRequest,
    AccessType,
    Integration,
    IntegrationProvider,
)
from app.models.onboarding import OnboardingRun
from app.models.talent import Professional
from app.models.user import User
from app.schemas.onboarding import OnboardingRunCreate
from app.schemas.talent import ProfessionalCreate
from app.services.access import AccessService
from app.services.audit import AuditService
from app.services.onboarding import OnboardingService
from app.services.people import PeopleService


@dataclass(frozen=True, slots=True)
class ToolAccessSpec:
    """Requested integration access for a newly enrolled professional."""

    integration_id: uuid.UUID | str
    access_type: AccessType | str | None = None
    role_or_scope: str = "member"


ToolAccessInput = ToolAccessSpec | Mapping[str, Any] | uuid.UUID | str


_PROVIDER_ACCESS_DEFAULTS = {
    IntegrationProvider.github: AccessType.repository,
    IntegrationProvider.slack: AccessType.channel,
    IntegrationProvider.trello: AccessType.board,
    IntegrationProvider.google_workspace: AccessType.drive,
    IntegrationProvider.m365: AccessType.drive,
}


class WorkforceOnboardingFacade:
    """Atomically coordinate workforce intake, onboarding, access, and audit."""

    def __init__(self, db: Session):
        self.db = db

    async def intake_and_enroll(
        self,
        *,
        tenant_id: uuid.UUID,
        operator: User,
        candidate_data: ProfessionalCreate,
        template_id: uuid.UUID,
        tool_requests: Iterable[ToolAccessInput] | None = None,
    ) -> tuple[Professional, OnboardingRun, list[AccessRequest]]:
        """Create and enroll a professional in one database transaction."""
        try:
            if operator.tenant_id != tenant_id:
                raise ValueError("Operator does not belong to the requested tenant.")

            professional = PeopleService(self.db).create_person(
                tenant_id=tenant_id,
                actor_id=operator.id,
                payload=candidate_data,
                commit=False,
            )

            onboarding_run = OnboardingService(self.db).start_onboarding_run(
                tenant_id=tenant_id,
                operator=operator,
                payload=OnboardingRunCreate(
                    professional_id=professional.id,
                    template_id=template_id,
                ),
                commit=False,
            )

            access_requests: list[AccessRequest] = []
            for tool_request in tool_requests or ():
                integration_id, access_type, role_or_scope = self._normalize_tool_request(
                    tenant_id=tenant_id,
                    tool_request=tool_request,
                )
                access_requests.append(
                    AccessService(self.db).create_request(
                        tenant_id=tenant_id,
                        professional_id=professional.id,
                        integration_id=integration_id,
                        access_type=access_type,
                        role_or_scope=role_or_scope,
                        requested_by=operator,
                        commit=False,
                    )
                )

            AuditService(self.db).log_event(
                tenant_id=tenant_id,
                actor_user_id=operator.id,
                action="workforce.intake_enrolled",
                target_type="Professional",
                target_id=professional.id,
                metadata={
                    "onboarding_run_id": str(onboarding_run.id),
                    "template_id": str(template_id),
                    "access_request_ids": [str(item.id) for item in access_requests],
                },
                commit=False,
            )

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(professional)
        self.db.refresh(onboarding_run)
        for access_request in access_requests:
            self.db.refresh(access_request)

        return professional, onboarding_run, access_requests

    def _normalize_tool_request(
        self,
        *,
        tenant_id: uuid.UUID,
        tool_request: ToolAccessInput,
    ) -> tuple[uuid.UUID, AccessType, str]:
        if isinstance(tool_request, ToolAccessSpec):
            integration_value = tool_request.integration_id
            access_type_value = tool_request.access_type
            role_or_scope = tool_request.role_or_scope
        elif isinstance(tool_request, Mapping):
            if "integration_id" not in tool_request:
                raise ValueError("Tool request requires an integration_id.")
            integration_value = tool_request["integration_id"]
            access_type_value = tool_request.get("access_type")
            role_or_scope = tool_request.get("role_or_scope", "member")
        else:
            integration_value = tool_request
            access_type_value = None
            role_or_scope = "member"

        try:
            integration_id = (
                integration_value
                if isinstance(integration_value, uuid.UUID)
                else uuid.UUID(str(integration_value))
            )
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("Tool request integration_id must be a valid UUID.") from exc

        integration = (
            self.db.query(Integration)
            .filter(
                Integration.id == integration_id,
                Integration.tenant_id == tenant_id,
            )
            .first()
        )
        if integration is None:
            raise LookupError("Integration not found in current tenant.")

        if access_type_value is None:
            access_type = _PROVIDER_ACCESS_DEFAULTS[integration.provider]
        else:
            try:
                access_type = (
                    access_type_value
                    if isinstance(access_type_value, AccessType)
                    else AccessType(str(access_type_value))
                )
            except ValueError as exc:
                raise ValueError("Unsupported access_type for tool request.") from exc

        if not isinstance(role_or_scope, str) or not role_or_scope.strip():
            raise ValueError("Tool request role_or_scope must be a non-empty string.")

        return integration.id, access_type, role_or_scope
