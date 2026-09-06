"""onboarding engine & access state machine DWOP-006 & DWOP-010

Revision ID: 003
Revises: 002
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    onboarding_run_status = postgresql.ENUM("in_progress", "blocked", "completed", name="onboarding_run_status")
    onboarding_run_status.create(op.get_bind(), checkfirst=True)
    onboarding_item_status = postgresql.ENUM("pending", "blocked", "completed", name="onboarding_item_status")
    onboarding_item_status.create(op.get_bind(), checkfirst=True)
    access_request_status = postgresql.ENUM("requested", "approved", "provisioning", "provisioned", "failed", "revoked", name="access_request_status")
    access_request_status.create(op.get_bind(), checkfirst=True)
    approval_outcome = postgresql.ENUM("approved", "rejected", name="approval_outcome")
    approval_outcome.create(op.get_bind(), checkfirst=True)
    access_type = postgresql.ENUM("repository", "channel", "board", "drive", "generic", name="access_type")
    access_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "onboarding_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_target", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_onboarding_templates_tenant_id", "onboarding_templates", ["tenant_id"])

    op.create_table(
        "checklist_template_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("onboarding_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_evidence_type", sa.String(50), nullable=False, server_default="none"),
        sa.Column("default_due_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_checklist_template_items_template_id", "checklist_template_items", ["template_id"])

    op.create_table(
        "onboarding_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("onboarding_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_manager_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", onboarding_run_status, nullable=False, server_default="in_progress"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_onboarding_runs_tenant_id", "onboarding_runs", ["tenant_id"])

    op.create_table(
        "onboarding_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("onboarding_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", onboarding_item_status, nullable=False, server_default="pending"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("blocker_reason", sa.Text(), nullable=True),
        sa.Column("evidence_ref", sa.String(500), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_onboarding_items_tenant_id", "onboarding_items", ["tenant_id"])
    op.create_index("ix_onboarding_items_run_id", "onboarding_items", ["run_id"])

    op.create_table(
        "integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False, server_default="github"),
        sa.Column("name", sa.String(255), nullable=False, server_default="default"),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_integrations_tenant_id", "integrations", ["tenant_id"])

    op.create_table(
        "access_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_type", access_type, nullable=False, server_default="generic"),
        sa.Column("role_or_scope", sa.String(255), nullable=False),
        sa.Column("status", access_request_status, nullable=False, server_default="requested"),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_access_requests_tenant_id", "access_requests", ["tenant_id"])
    op.create_index("ix_access_requests_status", "access_requests", ["status"])

    op.create_table(
        "approval_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_type", sa.String(50), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approver_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("outcome", approval_outcome, nullable=False),
        sa.Column("rationale", sa.String(1000), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_approval_decisions_tenant_id", "approval_decisions", ["tenant_id"])
    op.create_index("ix_approval_decisions_request_id", "approval_decisions", ["request_id"])


def downgrade() -> None:
    op.drop_table("approval_decisions")
    op.drop_table("access_requests")
    op.drop_table("integrations")
    op.drop_table("onboarding_items")
    op.drop_table("onboarding_runs")
    op.drop_table("checklist_template_items")
    op.drop_table("onboarding_templates")
    op.execute("DROP TYPE IF EXISTS access_type")
    op.execute("DROP TYPE IF EXISTS approval_outcome")
    op.execute("DROP TYPE IF EXISTS access_request_status")
    op.execute("DROP TYPE IF EXISTS onboarding_item_status")
    op.execute("DROP TYPE IF EXISTS onboarding_run_status")
