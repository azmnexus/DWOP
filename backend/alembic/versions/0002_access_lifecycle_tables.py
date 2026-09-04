"""create access lifecycle tables

Revision ID: 0002_access_lifecycle
Revises: 0001_org_structure
Create Date: 2026-09-04 01:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_access_lifecycle"
down_revision: Union[str, None] = "0001_org_structure"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("auth_type", sa.String(length=50), nullable=False),
        sa.Column("connection_status", sa.String(length=50), server_default="connected", nullable=False),
        sa.Column("health_status", sa.String(length=50), server_default="healthy", nullable=False),
        sa.Column("credentials_encrypted", _json(), nullable=False),
        sa.Column("scopes", _json(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_integrations_tenant_id"), "integrations", ["tenant_id"], unique=False)

    op.create_table(
        "access_requests",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("professional_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("integration_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("access_type", sa.String(length=50), nullable=False),
        sa.Column("role_or_scope", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="requested", nullable=False),
        sa.Column("requested_by_user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by_user_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for name in ("tenant_id", "professional_id", "integration_id", "status"):
        op.create_index(op.f(f"ix_access_requests_{name}"), "access_requests", [name], unique=False)

    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("request_type", sa.String(length=50), nullable=False),
        sa.Column("request_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("approver_user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("rationale", sa.String(length=1000), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_approval_decisions_tenant_id"), "approval_decisions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_approval_decisions_request_id"), "approval_decisions", ["request_id"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("metadata", _json(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for name in ("tenant_id", "actor_user_id", "action", "target_id", "timestamp"):
        op.create_index(op.f(f"ix_audit_events_{name}"), "audit_events", [name], unique=False)


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("approval_decisions")
    op.drop_table("access_requests")
    op.drop_table("integrations")
