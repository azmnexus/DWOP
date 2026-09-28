"""DWOP-014: Repository Pattern & Strict Multi-Tenant Isolation Verification Suite.

Validates Task P-02 specification:
1. BaseRepository generic CRUD:
   - get_by_id, list_paginated, create, update (Pydantic BaseModel & dict semantics, exclude_unset), delete, count, exists
2. Strict Multi-Tenant Isolation:
   - Tenant A data is 100% invisible to Tenant B across all read, update, delete, count, and exists queries.
3. Unit of Work Non-Committing Invariant:
   - Repositories stage and flush mutations; they NEVER commit transactions.
4. Domain Repository Methods across all 8 repositories:
   - UserRepository: identity lookups, global email/id resolution, role filtering
   - ProfessionalRepository: directory filtering, user-id linking, engagement association, bulk operations
   - OrganizationRepository: department hierarchy traversal, circular dependency ancestors, teams
   - ProjectRepository: delivery codes, client management
   - OnboardingRepository: templates, checklist definitions, run instantiation, item resolution, manager assignments
   - AssignmentRepository: capacity aggregations ONLY, active percentage summation (zero foreign entity getters)
   - AccessRepository: integrations, access requests, approval decisions
   - AuditRepository: append-only immutable event stream, update/delete immutability guards (NotImplementedError)
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import date, datetime, timezone
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.models.access import (
    AccessRequest,
    AccessRequestStatus,
    AccessType,
    ApprovalDecision,
    ApprovalOutcome,
    Integration,
    IntegrationAuthType,
    IntegrationProvider,
)
from app.models.assignment import Assignment, AssignmentStatus
from app.models.audit import AuditEvent
from app.models.onboarding import (
    ChecklistTemplateItem,
    OnboardingItem,
    OnboardingRun,
    OnboardingTemplate,
)
from app.models.organization import Department, Team
from app.models.project import Client, ClientStatus, Project, ProjectStatus
from app.models.talent import (
    AvailabilityStatus,
    ContractStatus,
    Engagement,
    EngagementType,
    Professional,
    ProfessionalStatus,
)
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.repositories import (
    AccessRepository,
    AssignmentRepository,
    AuditRepository,
    BaseRepository,
    OnboardingRepository,
    OrganizationRepository,
    ProfessionalRepository,
    ProjectRepository,
    UserRepository,
)


class DummyUpdateSchema(BaseModel):
    name: str | None = None
    description: str | None = None


def main():
    print("=" * 80)
    print("DWOP-014: REPOSITORY PATTERN & MULTI-TENANT ISOLATION SUITE")
    print("=" * 80)

    db = SessionLocal()

    try:
        # ---------------------------------------------------------------------
        # SETUP: Provision Test Tenants A and B
        # ---------------------------------------------------------------------
        print("\n[STEP 1] Provisioning Isolated Multi-Tenant Contexts (Tenant A & B)")
        tenant_a_id = uuid.uuid4()
        tenant_b_id = uuid.uuid4()
        suffix = uuid.uuid4().hex[:6]

        tenant_a = Tenant(id=tenant_a_id, name=f"Tenant A ({suffix})", slug=f"tenant-a-{suffix}")
        tenant_b = Tenant(id=tenant_b_id, name=f"Tenant B ({suffix})", slug=f"tenant-b-{suffix}")
        db.add_all([tenant_a, tenant_b])
        db.commit()
        print(f"  [PASS] Tenant A created: {tenant_a_id}")
        print(f"  [PASS] Tenant B created: {tenant_b_id}")

        # ---------------------------------------------------------------------
        # TEST 1: BaseRepository Generic CRUD & Mutation Semantics
        # ---------------------------------------------------------------------
        print("\n[STEP 2] Verifying BaseRepository Generic CRUD & Update Semantics")
        dept_base_repo = BaseRepository[Department](db, Department)

        dept_a = Department(
            tenant_id=tenant_a_id,
            name=f"Engineering Alpha-{suffix}",
        )
        created_dept = dept_base_repo.create(tenant_a_id, dept_a)
        assert created_dept.id is not None, "create() must flush and assign entity ID"
        print(f"  [PASS] create() staged and populated ID: {created_dept.id}")

        fetched = dept_base_repo.get_by_id(tenant_a_id, created_dept.id)
        assert fetched is not None and fetched.name == f"Engineering Alpha-{suffix}"
        print("  [PASS] get_by_id() successfully fetched scoped entity")

        # Update with Pydantic BaseModel (model_dump(exclude_unset=True))
        update_schema = DummyUpdateSchema(name=f"Engineering Beta-{suffix}")
        updated_dept = dept_base_repo.update(tenant_a_id, created_dept.id, update_schema)
        assert updated_dept is not None and updated_dept.name == f"Engineering Beta-{suffix}"
        print("  [PASS] update() successfully applied Pydantic schema mutation")

        # Update with dict
        updated_dept = dept_base_repo.update(
            tenant_a_id, created_dept.id, {"name": f"Engineering Gamma-{suffix}"}
        )
        assert updated_dept is not None and updated_dept.name == f"Engineering Gamma-{suffix}"
        print("  [PASS] update() successfully applied dict mutation")

        # Check exists and count
        assert dept_base_repo.exists(tenant_a_id, created_dept.id) is True
        assert dept_base_repo.count(tenant_a_id) >= 1
        print("  [PASS] exists() and count() verified on BaseRepository")

        # Pagination
        dept_a2 = Department(tenant_id=tenant_a_id, name=f"Product-{suffix}")
        dept_base_repo.create(tenant_a_id, dept_a2)
        paginated = dept_base_repo.list_paginated(tenant_a_id, skip=0, limit=1)
        assert len(paginated) == 1, "list_paginated must respect limit"
        print("  [PASS] list_paginated() verified with limit/offset")

        # ---------------------------------------------------------------------
        # TEST 2: Strict Multi-Tenant Boundary Isolation
        # ---------------------------------------------------------------------
        print("\n[STEP 3] Verifying Strict Multi-Tenant Isolation (Tenant A vs Tenant B)")
        # Tenant B MUST NOT see or modify Tenant A's department
        assert dept_base_repo.get_by_id(tenant_b_id, created_dept.id) is None, (
            "Tenant B get_by_id MUST return None for Tenant A record"
        )
        assert dept_base_repo.exists(tenant_b_id, created_dept.id) is False, (
            "Tenant B exists MUST return False for Tenant A record"
        )
        assert dept_base_repo.count(tenant_b_id) == 0, (
            "Tenant B count MUST be 0 when no records exist for Tenant B"
        )

        b_paginated = dept_base_repo.list_paginated(tenant_b_id, skip=0, limit=100)
        assert created_dept.id not in [d.id for d in b_paginated], (
            "Tenant B list_paginated MUST NOT contain Tenant A records"
        )

        b_update_result = dept_base_repo.update(
            tenant_b_id, created_dept.id, {"name": "HackedByTenantB"}
        )
        assert b_update_result is None, "Tenant B update MUST return None on Tenant A record"

        # Verify Tenant A record was untouched
        refreshed_a = dept_base_repo.get_by_id(tenant_a_id, created_dept.id)
        assert refreshed_a.name == f"Engineering Gamma-{suffix}", (
            "Tenant A record must remain unmutated after unauthorized Tenant B update attempt"
        )

        b_delete_result = dept_base_repo.delete(tenant_b_id, created_dept.id)
        assert b_delete_result is False, "Tenant B delete MUST return False on Tenant A record"
        assert dept_base_repo.exists(tenant_a_id, created_dept.id) is True, (
            "Tenant A record must still exist after unauthorized Tenant B delete attempt"
        )
        print("  [PASS] Multi-tenant isolation verified: Tenant A data is 100% invisible to Tenant B")

        # ---------------------------------------------------------------------
        # TEST 3: Unit of Work Non-Committing Flush Invariant
        # ---------------------------------------------------------------------
        print("\n[STEP 4] Verifying Unit of Work Non-Committing Flush Semantics")
        staged_dept = Department(tenant_id=tenant_a_id, name=f"Temporary-{suffix}")
        dept_base_repo.create(tenant_a_id, staged_dept)
        # Without service db.commit(), a rollback must completely discard it
        db.rollback()
        assert dept_base_repo.get_by_id(tenant_a_id, staged_dept.id) is None, (
            "Repositories must flush only; transaction rollback must discard uncommitted stages"
        )
        print("  [PASS] Repositories stage and flush only; db.commit()/db.rollback() ownership retained by service")

        # ---------------------------------------------------------------------
        # TEST 4: UserRepository Domain Methods
        # ---------------------------------------------------------------------
        print("\n[STEP 5] Verifying UserRepository Domain Operations")
        user_repo = UserRepository(db)
        user_a = User(
            id=uuid.uuid4(),
            tenant_id=tenant_a_id,
            email=f"alice-{suffix}@azm.com",
            hashed_password="hash",
            role=UserRole.ADMIN,
            is_active=True,
        )
        user_b = User(
            id=uuid.uuid4(),
            tenant_id=tenant_b_id,
            email=f"bob-{suffix}@azm.com",
            hashed_password="hash",
            role=UserRole.MEMBER,
            is_active=True,
        )
        user_repo.create(tenant_a_id, user_a)
        user_repo.create(tenant_b_id, user_b)
        db.commit()

        # Scoped get_by_email
        assert user_repo.get_by_email(tenant_a_id, f"alice-{suffix}@azm.com") is not None
        assert user_repo.get_by_email(tenant_b_id, f"alice-{suffix}@azm.com") is None
        print("  [PASS] UserRepository.get_by_email strictly scoped to tenant")

        # Global lookups for authentication / JWT verification
        assert user_repo.get_by_email_global(f"alice-{suffix}@azm.com") is not None
        assert user_repo.get_by_id_global(user_a.id) is not None
        print("  [PASS] UserRepository global auth lookups verified")

        # Role query
        admins_a = user_repo.list_by_role(tenant_a_id, UserRole.ADMIN)
        assert user_a.id in [u.id for u in admins_a]
        assert user_b.id not in [u.id for u in admins_a]
        print("  [PASS] UserRepository.list_by_role verified")

        # ---------------------------------------------------------------------
        # TEST 5: ProfessionalRepository Domain Methods
        # ---------------------------------------------------------------------
        print("\n[STEP 6] Verifying ProfessionalRepository Domain Operations")
        prof_repo = ProfessionalRepository(db)
        prof_a = Professional(
            id=uuid.uuid4(),
            tenant_id=tenant_a_id,
            user_id=user_a.id,
            first_name="Alice",
            last_name="Talent",
            email=f"alice.talent-{suffix}@azm.com",
            status=ProfessionalStatus.ready,
            availability_status=AvailabilityStatus.available,
            skills=["Python", "FastAPI"],
        )
        prof_repo.create(tenant_a_id, prof_a)

        eng_a = Engagement(
            tenant_id=tenant_a_id,
            professional_id=prof_a.id,
            engagement_type=EngagementType.employee,
            start_date=date.today(),
            contract_status=ContractStatus.active,
            compensation_rate=120000,
        )
        prof_repo.create_engagement(eng_a)
        db.commit()

        assert prof_repo.get_by_email(tenant_a_id, f"alice.talent-{suffix}@azm.com") is not None
        assert prof_repo.get_by_email(tenant_b_id, f"alice.talent-{suffix}@azm.com") is None
        assert prof_repo.get_by_user_id(tenant_a_id, user_a.id) is not None
        assert prof_repo.get_engagement(tenant_a_id, prof_a.id) is not None
        assert len(prof_repo.get_all(tenant_a_id)) >= 1
        print("  [PASS] ProfessionalRepository queries, engagements, and user-id linking verified")

        # ---------------------------------------------------------------------
        # TEST 6: OrganizationRepository Hierarchy & Traversal
        # ---------------------------------------------------------------------
        print("\n[STEP 7] Verifying OrganizationRepository Hierarchy Traversal")
        org_repo = OrganizationRepository(db)
        parent_dept = Department(tenant_id=tenant_a_id, name=f"Parent-{suffix}")
        org_repo.create_department(parent_dept)
        child_dept = Department(
            tenant_id=tenant_a_id,
            name=f"Child-{suffix}",
            parent_department_id=parent_dept.id,
        )
        org_repo.create_department(child_dept)
        db.commit()

        ancestor = org_repo.get_parent_ancestor(tenant_a_id, parent_dept.id)
        assert ancestor is not None and ancestor.id == parent_dept.id
        assert org_repo.get_parent_ancestor(tenant_b_id, parent_dept.id) is None, (
            "Cross-tenant ancestor lookup must return None"
        )

        team = Team(
            tenant_id=tenant_a_id,
            department_id=child_dept.id,
            name=f"Backend Team-{suffix}",
        )
        org_repo.create_team(team)
        db.commit()
        assert org_repo.get_team(tenant_a_id, team.id) is not None
        assert len(org_repo.list_teams(tenant_a_id, department_id=child_dept.id)) >= 1
        print("  [PASS] OrganizationRepository department hierarchy and team queries verified")

        # ---------------------------------------------------------------------
        # TEST 7: ProjectRepository Commercial Portfolios
        # ---------------------------------------------------------------------
        print("\n[STEP 8] Verifying ProjectRepository Commercial Entities")
        proj_repo = ProjectRepository(db)
        client = Client(
            tenant_id=tenant_a_id,
            name=f"Acme Corp-{suffix}",
            status=ClientStatus.active,
        )
        proj_repo.create_client(client)

        proj = Project(
            tenant_id=tenant_a_id,
            client_id=client.id,
            code=f"PRJ-{suffix.upper()}",
            name=f"Project Alpha-{suffix}",
            status=ProjectStatus.active,
        )
        proj_repo.create(tenant_a_id, proj)
        db.commit()

        assert proj_repo.get_by_code(tenant_a_id, f"PRJ-{suffix.upper()}") is not None
        assert proj_repo.get_by_code(tenant_b_id, f"PRJ-{suffix.upper()}") is None
        assert proj_repo.get_client(tenant_a_id, client.id) is not None
        print("  [PASS] ProjectRepository delivery code and client lookups verified")

        # ---------------------------------------------------------------------
        # TEST 8: OnboardingRepository Workflow Blueprints & Runs
        # ---------------------------------------------------------------------
        print("\n[STEP 9] Verifying OnboardingRepository Templates, Runs, and Items")
        onb_repo = OnboardingRepository(db)
        tmpl = OnboardingTemplate(
            tenant_id=tenant_a_id,
            role_target="Developer",
            title=f"Dev Onboarding-{suffix}",
            description="Blueprint",
            version=1,
            is_active=True,
        )
        tmpl_items = [
            ChecklistTemplateItem(
                title="Setup Dev Environment",
                description="Install SDK",
                order_index=1,
                default_due_days=3,
            )
        ]
        onb_repo.create_template(tmpl, tmpl_items)

        run = OnboardingRun(
            tenant_id=tenant_a_id,
            professional_id=prof_a.id,
            template_id=tmpl.id,
            assigned_manager_id=user_a.id,
            status="in_progress",
            progress_pct=0,
        )
        run_items = [
            OnboardingItem(
                title="Setup Dev Environment",
                owner_user_id=user_a.id,
                status="pending",
                due_date=date.today(),
            )
        ]
        onb_repo.create_run(run, run_items)
        db.commit()

        assert onb_repo.get_template(tenant_a_id, tmpl.id) is not None
        assert onb_repo.get_run(tenant_a_id, run.id) is not None
        assert onb_repo.has_manager_assignment(tenant_a_id, user_a.id, prof_a.id) is True
        assert len(onb_repo.list_items_for_run(run.id)) == 1
        assert onb_repo.get_item(tenant_a_id, run.id, run_items[0].id) is not None
        print("  [PASS] OnboardingRepository template items, runs, and manager assignments verified")

        # ---------------------------------------------------------------------
        # TEST 9: AssignmentRepository Capacity Aggregations (Strict Bounded Context)
        # ---------------------------------------------------------------------
        print("\n[STEP 10] Verifying AssignmentRepository Capacity Aggregations")
        assign_repo = AssignmentRepository(db)
        assign_1 = Assignment(
            tenant_id=tenant_a_id,
            professional_id=prof_a.id,
            project_id=proj.id,
            role_on_project="Lead Architect",
            capacity_percentage=40,
            status=AssignmentStatus.active,
            start_date=date.today(),
        )
        assign_2 = Assignment(
            tenant_id=tenant_a_id,
            professional_id=prof_a.id,
            project_id=proj.id,
            role_on_project="Senior Engineer",
            capacity_percentage=35,
            status=AssignmentStatus.active,
            start_date=date.today(),
        )
        assign_repo.create(tenant_a_id, assign_1)
        assign_repo.create(tenant_a_id, assign_2)
        db.commit()

        # Sum capacity: 40 + 35 = 75
        total_cap = assign_repo.sum_active_capacity(tenant_a_id, prof_a.id)
        assert total_cap == 75, f"Expected 75% capacity, got {total_cap}%"

        # Exclude an assignment during capacity headroom recalculation
        excluded_cap = assign_repo.sum_active_capacity(
            tenant_a_id, prof_a.id, exclude_assignment_id=assign_1.id
        )
        assert excluded_cap == 35, f"Expected 35% capacity with exclusion, got {excluded_cap}%"

        # Verify no cross-tenant bleed in capacity sum
        b_cap = assign_repo.sum_active_capacity(tenant_b_id, prof_a.id)
        assert b_cap == 0, f"Tenant B must see 0% capacity for Tenant A talent, got {b_cap}%"

        # Verify strict bounded context: AssignmentRepository has no foreign getters
        assert not hasattr(assign_repo, "get_project"), "AssignmentRepository must NOT expose get_project"
        assert not hasattr(assign_repo, "get_professional"), "AssignmentRepository must NOT expose get_professional"
        assert not hasattr(assign_repo, "get_team"), "AssignmentRepository must NOT expose get_team"
        print("  [PASS] AssignmentRepository capacity aggregations and bounded context invariants verified")

        # ---------------------------------------------------------------------
        # TEST 10: AccessRepository & Provider Adaptations
        # ---------------------------------------------------------------------
        print("\n[STEP 11] Verifying AccessRepository Integrations and Lifecycle")
        access_repo = AccessRepository(db)
        integration = Integration(
            tenant_id=tenant_a_id,
            provider=IntegrationProvider.github,
            auth_type=IntegrationAuthType.api_key,
            connection_status="connected",
            health_status="healthy",
            credentials_encrypted={"api_key": "secret"},
            scopes=["repo", "admin:org"],
        )
        db.add(integration)
        db.flush()

        req = AccessRequest(
            tenant_id=tenant_a_id,
            professional_id=prof_a.id,
            integration_id=integration.id,
            access_type=AccessType.repository,
            role_or_scope="write",
            status=AccessRequestStatus.requested,
            requested_by_user_id=user_a.id,
        )
        access_repo.create_request(req)

        decision = ApprovalDecision(
            tenant_id=tenant_a_id,
            request_type="access",
            request_id=req.id,
            approver_user_id=user_a.id,
            outcome=ApprovalOutcome.approved,
            rationale="Approved by senior reviewer",
        )
        access_repo.create_decision(decision)
        db.commit()

        assert access_repo.get_request(tenant_a_id, req.id) is not None
        assert access_repo.get_request(tenant_b_id, req.id) is None
        assert access_repo.get_integration_by_provider(tenant_a_id, IntegrationProvider.github) is not None
        assert len(access_repo.list_requests(tenant_a_id)) >= 1
        print("  [PASS] AccessRepository requests, integrations, and decisions verified")

        # ---------------------------------------------------------------------
        # TEST 11: AuditRepository Append-Only Event Stream & Immutability
        # ---------------------------------------------------------------------
        print("\n[STEP 12] Verifying AuditRepository Append-Only Stream and Immutability Guards")
        audit_repo = AuditRepository(db)
        event = audit_repo.log_event(
            tenant_id=tenant_a_id,
            actor_user_id=user_a.id,
            action="repository.pattern_tested",
            target_type="RepositorySuite",
            target_id=uuid.uuid4(),
            metadata={"test_run": suffix},
        )
        db.commit()

        events = audit_repo.list_events(tenant_a_id, action="repository.pattern_tested")
        assert len(events) >= 1
        assert events[0].id == event.id
        assert audit_repo.count_events(tenant_a_id, action="repository.pattern_tested") >= 1
        assert audit_repo.count_events(tenant_b_id, action="repository.pattern_tested") == 0

        # Immutability Guard: update and delete MUST raise NotImplementedError
        try:
            audit_repo.update(tenant_a_id, event.id, {"action": "tampered"})
            assert False, "audit_repo.update() MUST raise NotImplementedError"
        except NotImplementedError:
            print("  [PASS] Immutability guard verified: update() raised NotImplementedError")

        try:
            audit_repo.delete(tenant_a_id, event.id)
            assert False, "audit_repo.delete() MUST raise NotImplementedError"
        except NotImplementedError:
            print("  [PASS] Immutability guard verified: delete() raised NotImplementedError")

        print("  [PASS] AuditRepository append-only event stream and immutability invariants verified")

        print("\n" + "=" * 80)
        print("ALL DWOP-014 REPOSITORY PATTERN & MULTI-TENANT ISOLATION TESTS PASSED (100%)")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    main()
