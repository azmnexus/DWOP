"""workforce intake and assignments DWOP-005 & DWOP-009

Revision ID: 002
Revises: 001
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    professional_status = postgresql.ENUM(
        "intake", "onboarding", "ready", "assigned", "offboarding", "inactive", name="professional_status"
    )
    professional_status.create(op.get_bind(), checkfirst=True)

    availability_status = postgresql.ENUM(
        "available", "partially_booked", "fully_booked", name="availability_status"
    )
    availability_status.create(op.get_bind(), checkfirst=True)

    engagement_type = postgresql.ENUM(
        "employee", "contractor", "working_student", name="engagement_type"
    )
    engagement_type.create(op.get_bind(), checkfirst=True)

    contract_status = postgresql.ENUM("active", "expired", "terminated", name="contract_status")
    contract_status.create(op.get_bind(), checkfirst=True)

    assignment_status = postgresql.ENUM("planned", "active", "completed", "cancelled", name="assignment_status")
    assignment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "professionals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("status", professional_status, nullable=False, server_default="intake"),
        sa.Column("availability_status", availability_status, nullable=False, server_default="available"),
        sa.Column("skills", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_professionals_tenant_id", "professionals", ["tenant_id"])
    op.create_index("ix_professionals_email", "professionals", ["email"])

    op.create_table(
        "engagements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engagement_type", engagement_type, nullable=False, server_default="contractor"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("contract_status", contract_status, nullable=False, server_default="active"),
        sa.Column("compensation_rate", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_engagements_tenant_id", "engagements", ["tenant_id"])
    op.create_index("ix_engagements_professional_id", "engagements", ["professional_id"])

    op.create_table(
        "assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role_on_project", sa.String(100), nullable=True),
        sa.Column("capacity_percentage", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", assignment_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_assignments_tenant_id", "assignments", ["tenant_id"])
    op.create_index("ix_assignments_professional_id", "assignments", ["professional_id"])
    op.create_index("ix_assignments_project_id", "assignments", ["project_id"])


def downgrade() -> None:
    op.drop_table("assignments")
    op.drop_table("engagements")
    op.drop_table("professionals")
    op.execute("DROP TYPE IF EXISTS assignment_status")
    op.execute("DROP TYPE IF EXISTS contract_status")
    op.execute("DROP TYPE IF EXISTS engagement_type")
    op.execute("DROP TYPE IF EXISTS availability_status")
    op.execute("DROP TYPE IF EXISTS professional_status")
