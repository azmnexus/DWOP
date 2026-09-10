"""Verify the default GitHub sandbox integration seed is safe and idempotent."""
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import Base
import app.models  # noqa: F401 -- register all model tables
from app.models.access import Integration, IntegrationAuthType, IntegrationProvider
from app.models.tenant import Tenant
from scripts.seed_org_structure import seed_default_github_integration


def main() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    tenant = Tenant(name="AZM Seed Test", slug="azm-seed-test")
    other_tenant = Tenant(name="Other Seed Test", slug="other-seed-test")
    db.add_all([tenant, other_tenant])
    db.commit()

    first, first_created = seed_default_github_integration(db, tenant)
    second, second_created = seed_default_github_integration(db, tenant)
    other_first, other_first_created = seed_default_github_integration(
        db, other_tenant
    )
    other_second, other_second_created = seed_default_github_integration(
        db, other_tenant
    )

    assert first_created is True
    assert second_created is False
    assert other_first_created is True
    assert other_second_created is False
    assert first.id == second.id
    assert other_first.id == other_second.id
    assert first.id != other_first.id
    assert first.tenant_id == tenant.id
    assert other_first.tenant_id == other_tenant.id
    assert first.provider == IntegrationProvider.github
    assert first.auth_type == IntegrationAuthType.oauth2
    assert first.connection_status == "connected"
    assert first.health_status == "healthy"
    assert first.credentials_encrypted == {}
    assert first.scopes == ["repo"]
    assert (
        db.query(Integration)
        .filter(
            Integration.tenant_id == tenant.id,
            Integration.provider == IntegrationProvider.github,
        )
        .count()
        == 1
    )
    assert db.query(Integration).count() == 2
    print(
        "[PASS] Default GitHub sandbox integration seed is safe, "
        "tenant-isolated, and idempotent"
    )


if __name__ == "__main__":
    main()
