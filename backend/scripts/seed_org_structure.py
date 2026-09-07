"""Seed script for DWOP-003, DWOP-004, DWOP-005 & DWOP-006:
- Root Tenant: AZM Nexus (with branding jsonb)
- Default GitHub sandbox integration for access lifecycle demos
- Admin User: admin@azm-nexus.com (role: ADMIN, password: Admin123!)
- Standard Member: member@azm-nexus.com (role: MEMBER, password: Member123!)
- Manager User: atanda.david@azm-nexus.com (role: MANAGER, password: LeadAtanda2026!)
- Departments: Executive Leadership, Core Platform & Engineering
- Teams: Backend & Cloud Architecture, Frontend & Workforce Experience
- Client: Apex Global Banking Group
- Project: DWOP Platform Foundation (DWOP-CORE)
- Professionals (3 sample intake records): Jane Doe, John Smith, Alice Johnson
- Onboarding Template: Standard Software Engineer v2.1 (5 checklist items)
- Active Onboarding Run: Jane Doe instantiated with 5 live checklist tasks
"""
import sys
import os

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.core.database import engine, SessionLocal, Base
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.organization import Department, Team
from app.models.project import Client, Project, ClientStatus, ProjectStatus
from app.models.talent import (
    Professional,
    Engagement,
    ProfessionalStatus,
    AvailabilityStatus,
    EngagementType,
    ContractStatus,
)
from app.models.onboarding import (
    OnboardingTemplate,
    ChecklistTemplateItem,
    OnboardingRun,
    OnboardingItem,
)
from app.models.access import Integration, IntegrationAuthType, IntegrationProvider


def seed_default_github_integration(
    db: Session, tenant: Tenant
) -> tuple[Integration, bool]:
    """Ensure the tenant has one network-free GitHub demo integration."""
    integration = (
        db.query(Integration)
        .filter(
            Integration.tenant_id == tenant.id,
            Integration.provider == IntegrationProvider.github,
        )
        .first()
    )
    if integration:
        return integration, False

    integration = Integration(
        tenant_id=tenant.id,
        provider=IntegrationProvider.github,
        auth_type=IntegrationAuthType.oauth2,
        connection_status="connected",
        health_status="healthy",
        credentials_encrypted={},
        scopes=["repo"],
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration, True


def seed():
    from app.core.security import get_password_hash

    print("[1/8] Ensuring database tables are created...")
    Base.metadata.create_all(bind=engine)
    print("      Tables verified successfully.")

    db = SessionLocal()
    try:
        print("[2/8] Seeding Root Tenant: AZM Nexus...")
        tenant = db.query(Tenant).filter(Tenant.slug == "azm-nexus").first()
        if not tenant:
            tenant = Tenant(
                name="AZM Nexus",
                slug="azm-nexus",
                domain="azm-nexus.com",
                plan_tier="enterprise",
                branding={
                    "theme": "diamond_sapphire",
                    "primary_color": "#2563EB",
                    "accent_shimmer": "#38BDF8",
                    "logo_url": "/brand/azm-diamond.svg",
                },
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"      Created Tenant: {tenant.name} (ID: {tenant.id})")
        else:
            print(f"      Tenant already exists: {tenant.name} (ID: {tenant.id})")

        print("[3/8] Seeding Default GitHub Sandbox Integration...")
        github_integration, created = seed_default_github_integration(db, tenant)
        action = "Created" if created else "Already exists"
        print(
            f"      {action}: GitHub sandbox integration "
            f"(ID: {github_integration.id})"
        )

        print("[4/8] Seeding Users with HASHED Passwords (Admin, Member, Manager)...")
        # 1. Admin user
        admin_user = db.query(User).filter(User.email == "admin@azm-nexus.com").first()
        admin_hashed = get_password_hash("Admin123!")
        if not admin_user:
            admin_user = User(
                tenant_id=tenant.id,
                email="admin@azm-nexus.com",
                hashed_password=admin_hashed,
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin_user)
        else:
            admin_user.hashed_password = admin_hashed
            admin_user.role = UserRole.ADMIN

        # 2. Standard Member user
        member_user = db.query(User).filter(User.email == "member@azm-nexus.com").first()
        member_hashed = get_password_hash("Member123!")
        if not member_user:
            member_user = User(
                tenant_id=tenant.id,
                email="member@azm-nexus.com",
                hashed_password=member_hashed,
                role=UserRole.MEMBER,
                is_active=True,
            )
            db.add(member_user)
        else:
            member_user.hashed_password = member_hashed
            member_user.role = UserRole.MEMBER

        # 3. Atanda David - ADMIN (Systems Architect / Super Admin per Document Section 2)
        atanda_user = db.query(User).filter(User.email == "atanda.david@azm-nexus.com").first()
        atanda_hashed = get_password_hash("LeadAtanda2026!")
        if not atanda_user:
            atanda_user = User(
                tenant_id=tenant.id,
                email="atanda.david@azm-nexus.com",
                hashed_password=atanda_hashed,
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(atanda_user)
        else:
            atanda_user.hashed_password = atanda_hashed
            atanda_user.role = UserRole.ADMIN

        # 4. Manager user (for demo: retains MANAGER role tier)
        manager_user = db.query(User).filter(User.email == "manager@azm-nexus.com").first()
        manager_hashed = get_password_hash("Manager123!")
        if not manager_user:
            manager_user = User(
                tenant_id=tenant.id,
                email="manager@azm-nexus.com",
                hashed_password=manager_hashed,
                role=UserRole.MANAGER,
                is_active=True,
            )
            db.add(manager_user)
        else:
            manager_user.hashed_password = manager_hashed
            manager_user.role = UserRole.MANAGER

        db.commit()
        db.refresh(admin_user)
        db.refresh(member_user)
        db.refresh(atanda_user)
        db.refresh(manager_user)

        print(f"      Admin:   {admin_user.email} (Role: {admin_user.role.value})")
        print(f"      Atanda:  {atanda_user.email} (Role: {atanda_user.role.value})")
        print(f"      Manager: {manager_user.email} (Role: {manager_user.role.value})")
        print(f"      Member:  {member_user.email} (Role: {member_user.role.value})")

        print("[5/8] Seeding Departments and Teams...")
        exec_dept = (
            db.query(Department)
            .filter(Department.tenant_id == tenant.id, Department.name == "Executive Leadership")
            .first()
        )
        if not exec_dept:
            exec_dept = Department(
                tenant_id=tenant.id,
                name="Executive Leadership",
                manager_user_id=admin_user.id,
            )
            db.add(exec_dept)
            db.commit()
            db.refresh(exec_dept)

        eng_dept = (
            db.query(Department)
            .filter(Department.tenant_id == tenant.id, Department.name == "Core Platform & Engineering")
            .first()
        )
        if not eng_dept:
            eng_dept = Department(
                tenant_id=tenant.id,
                name="Core Platform & Engineering",
                manager_user_id=atanda_user.id,
                parent_department_id=exec_dept.id,
            )
            db.add(eng_dept)
            db.commit()
            db.refresh(eng_dept)

        backend_team = (
            db.query(Team)
            .filter(Team.tenant_id == tenant.id, Team.name == "Backend & Cloud Architecture")
            .first()
        )
        if not backend_team:
            backend_team = Team(
                tenant_id=tenant.id,
                department_id=eng_dept.id,
                name="Backend & Cloud Architecture",
                team_lead_id=atanda_user.id,
            )
            db.add(backend_team)

        frontend_team = (
            db.query(Team)
            .filter(Team.tenant_id == tenant.id, Team.name == "Frontend & Workforce Experience")
            .first()
        )
        if not frontend_team:
            frontend_team = Team(
                tenant_id=tenant.id,
                department_id=eng_dept.id,
                name="Frontend & Workforce Experience",
                team_lead_id=None,
            )
            db.add(frontend_team)

        db.commit()
        print(f"      Departments: {exec_dept.name}, {eng_dept.name}")
        print("      Teams: Backend & Cloud Architecture, Frontend & Workforce Experience")

        print("[6/8] Seeding Client and Project...")
        client = (
            db.query(Client)
            .filter(Client.tenant_id == tenant.id, Client.name == "Apex Global Banking Group")
            .first()
        )
        if not client:
            client = Client(
                tenant_id=tenant.id,
                name="Apex Global Banking Group",
                contact_email="procurement@apex-banking.example.com",
                status=ClientStatus.active,
            )
            db.add(client)
            db.commit()
            db.refresh(client)

        project = (
            db.query(Project)
            .filter(Project.tenant_id == tenant.id, Project.code == "DWOP-CORE")
            .first()
        )
        if not project:
            project = Project(
                tenant_id=tenant.id,
                client_id=client.id,
                name="DWOP Platform Foundation",
                code="DWOP-CORE",
                status=ProjectStatus.active,
                start_date=date(2026, 9, 1),
                target_end_date=date(2026, 12, 31),
            )
            db.add(project)
            db.commit()
            db.refresh(project)

        print(f"      Client: {client.name} (ID: {client.id})")
        print(f"      Project: {project.name} [{project.code}] (ID: {project.id})")

        print("[7/8] Seeding Sample Professionals (Intake Status)...")
        sample_professionals = [
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane.doe@azm-nexus.com",
                "phone": "+234 801 234 5678",
                "status": ProfessionalStatus.intake,
                "availability": AvailabilityStatus.available,
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "SQLAlchemy"],
                "engagement_type": EngagementType.contractor,
                "rate": "$85/hr",
            },
            {
                "first_name": "John",
                "last_name": "Smith",
                "email": "john.smith@azm-nexus.com",
                "phone": "+234 802 345 6789",
                "status": ProfessionalStatus.intake,
                "availability": AvailabilityStatus.available,
                "skills": ["React", "Next.js", "TypeScript", "TailwindCSS", "REST APIs"],
                "engagement_type": EngagementType.employee,
                "rate": "$90,000/yr",
            },
            {
                "first_name": "Alice",
                "last_name": "Johnson",
                "email": "alice.johnson@azm-nexus.com",
                "phone": "+234 803 456 7890",
                "status": ProfessionalStatus.intake,
                "availability": AvailabilityStatus.available,
                "skills": ["DevOps", "AWS", "Terraform", "Kubernetes", "GitHub Actions"],
                "engagement_type": EngagementType.contractor,
                "rate": "$95/hr",
            },
        ]

        jane_prof = None
        for p_data in sample_professionals:
            prof = (
                db.query(Professional)
                .filter(Professional.email == p_data["email"], Professional.tenant_id == tenant.id)
                .first()
            )
            if not prof:
                prof = Professional(
                    tenant_id=tenant.id,
                    first_name=p_data["first_name"],
                    last_name=p_data["last_name"],
                    email=p_data["email"],
                    phone=p_data["phone"],
                    status=p_data["status"],
                    availability_status=p_data["availability"],
                    skills=p_data["skills"],
                )
                db.add(prof)
                db.flush()

                eng = Engagement(
                    tenant_id=tenant.id,
                    professional_id=prof.id,
                    engagement_type=p_data["engagement_type"],
                    start_date=date(2026, 9, 1),
                    contract_status=ContractStatus.active,
                    compensation_rate=p_data["rate"],
                )
                db.add(eng)
                print(f"      Created Professional: {prof.first_name} {prof.last_name} ({prof.email}) [Status: {prof.status.value}]")
            else:
                print(f"      Professional already exists: {prof.first_name} {prof.last_name}")

            if prof.email == "jane.doe@azm-nexus.com":
                jane_prof = prof

        db.commit()

        print("[8/8] Seeding Walid's Mock Onboarding Template & Active Run for Jane Doe...")
        template_title = "Standard Software Engineer Onboarding v2.1"
        template = (
            db.query(OnboardingTemplate)
            .filter(OnboardingTemplate.tenant_id == tenant.id, OnboardingTemplate.title == template_title)
            .first()
        )

        mock_checklist_items = [
            {
                "order_index": 1,
                "title": "Sign Confidentiality & Non-Disclosure Agreement (NDA)",
                "description": "Download, sign, and upload countersigned corporate NDA.",
                "required_evidence_type": "signed_pdf",
                "default_due_days": 1,
            },
            {
                "order_index": 2,
                "title": "Setup Corporate GitHub & Enforce Hardware 2FA",
                "description": "Configure GitHub organization access and register FIDO2 security key.",
                "required_evidence_type": "screenshot",
                "default_due_days": 2,
            },
            {
                "order_index": 3,
                "title": "Complete InfoSec & OWASP Compliance Briefing",
                "description": "Review AZM security guidelines, credential hygiene, and zero-trust policies.",
                "required_evidence_type": "none",
                "default_due_days": 3,
            },
            {
                "order_index": 4,
                "title": "Development Environment Setup & Local Docker Run",
                "description": "Clone DWOP monorepo, build local Docker stack, and verify health endpoint.",
                "required_evidence_type": "screenshot",
                "default_due_days": 4,
            },
            {
                "order_index": 5,
                "title": "Team Orientation & Engineering Manager 1:1 Sync",
                "description": "Meet with Lead Architect / Manager Atanda David for sprint alignment.",
                "required_evidence_type": "none",
                "default_due_days": 5,
            },
        ]

        if not template:
            template = OnboardingTemplate(
                tenant_id=tenant.id,
                role_target="Software Engineer",
                title=template_title,
                description="Authoritative onboarding blueprint for incoming software engineers and backend architects.",
                version=2,
                is_active=True,
            )
            db.add(template)
            db.flush()

            for item_data in mock_checklist_items:
                item = ChecklistTemplateItem(
                    template_id=template.id,
                    title=item_data["title"],
                    description=item_data["description"],
                    order_index=item_data["order_index"],
                    required_evidence_type=item_data["required_evidence_type"],
                    default_due_days=item_data["default_due_days"],
                )
                db.add(item)
            db.commit()
            db.refresh(template)
            print(f"      Created Template: '{template.title}' with {len(mock_checklist_items)} blueprint items.")
        else:
            print(f"      Template already exists: '{template.title}' (ID: {template.id})")

        # Auto-trigger OnboardingRun for Jane Doe
        if jane_prof:
            active_run = (
                db.query(OnboardingRun)
                .filter(OnboardingRun.professional_id == jane_prof.id, OnboardingRun.tenant_id == tenant.id)
                .first()
            )
            if not active_run:
                active_run = OnboardingRun(
                    tenant_id=tenant.id,
                    professional_id=jane_prof.id,
                    template_id=template.id,
                    assigned_manager_id=atanda_user.id,
                    status="in_progress",
                    progress_pct=0,
                )
                db.add(active_run)
                db.flush()

                # Advance Jane Doe status to onboarding
                jane_prof.status = ProfessionalStatus.onboarding

                # Auto-generate the 5 OnboardingItems
                today = date.today()
                for t_item in template.items:
                    due = today + timedelta(days=t_item.default_due_days)
                    run_task = OnboardingItem(
                        run_id=active_run.id,
                        title=t_item.title,
                        owner_user_id=atanda_user.id,
                        status="pending",
                        due_date=due,
                    )
                    db.add(run_task)

                db.commit()
                db.refresh(active_run)
                print(f"      Auto-triggered active OnboardingRun for Jane Doe! (Run ID: {active_run.id}, Tasks: 5)")
            else:
                print(f"      Active OnboardingRun already exists for Jane Doe (Run ID: {active_run.id})")

        print("\n" + "=" * 70)
        print("DWOP-006 SEEDING COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print(f"TENANT ID: {tenant.id}")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    seed()
