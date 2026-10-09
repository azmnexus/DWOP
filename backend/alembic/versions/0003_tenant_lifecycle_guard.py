"""add tenants.is_active for ADR-002 hybrid offboarding guard

Revision ID: 0003_tenant_lifecycle_guard
Revises: 0002_access_lifecycle
Create Date: 2026-10-05 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_tenant_lifecycle_guard"
down_revision: Union[str, None] = "0002_access_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADR-002 Phase 3: the hybrid offboarding guard verifies Tenant.is_active in
    # the same single query that verifies User.is_active, so a suspended tenant
    # revokes every session beneath it without waiting for JWT expiry.
    op.add_column(
        "tenants",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    # Supports the guard query's "active users in tenant" filtering paths.
    op.create_index(
        op.f("ix_users_tenant_id_is_active"),
        "users",
        ["tenant_id", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_users_tenant_id_is_active"), table_name="users")
    op.drop_column("tenants", "is_active")
