"""close ERD gaps: tables 17/18, integration enums, assignment/client enum alignment

Revision ID: 005
Revises: 004
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enum alignment: add missing values ---
    # AssignmentStatus.reassigned
    op.execute("ALTER TYPE assignment_status ADD VALUE IF NOT EXISTS 'reassigned'")
    # ClientStatus.CHURNED
    op.execute("ALTER TYPE client_status ADD VALUE IF NOT EXISTS 'CHURNED'")
    # Integration enums (if not already created by previous stub)
    op.execute("DO $$ BEGIN CREATE TYPE integration_auth_type AS ENUM ('oauth2','api_key','webhook'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE integration_connection_status AS ENUM ('connected','disconnected','error'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    acknowledgement_status = postgresql.ENUM("pending", "acknowledged", name="acknowledgement_status")
    acknowledgement_status.create(op.get_bind(), checkfirst=True)

    notification_channel = postgresql.ENUM("email", "slack", "in_app", name="notification_channel")
    notification_channel.create(op.get_bind(), checkfirst=True)

    notification_status = postgresql.ENUM("pending", "sent", "failed", name="notification_status")
    notification_status.create(op.get_bind(), checkfirst=True)

    # --- Integrations: add 5 columns + updated_at + provider width ---
    # Add new columns if not exists (idempotent pattern)
    op.execute("ALTER TABLE integrations ADD COLUMN IF NOT EXISTS auth_type integration_auth_type NOT NULL DEFAULT 'oauth2'")
    op.execute("ALTER TABLE integrations ADD COLUMN IF NOT EXISTS connection_status VARCHAR(50) NOT NULL DEFAULT 'disconnected'")
    op.execute("ALTER TABLE integrations ADD COLUMN IF NOT EXISTS health_status VARCHAR(50) NOT NULL DEFAULT 'unknown'")
    op.execute("ALTER TABLE integrations ADD COLUMN IF NOT EXISTS credentials_encrypted JSONB DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE integrations ADD COLUMN IF NOT EXISTS scopes JSONB DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE integrations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()")

    # Tighten provider width 100 -> 50 (safe as data fits)
    op.execute("ALTER TABLE integrations ALTER COLUMN provider TYPE VARCHAR(50) USING provider::VARCHAR(50)")

    # --- Table 17: document_acknowledgements ---
    op.create_table(
        "document_acknowledgements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_title", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False, server_default="v1.0"),
        sa.Column("status", acknowledgement_status, nullable=False, server_default="pending"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_document_acknowledgements_tenant_id", "document_acknowledgements", ["tenant_id"])
    op.create_index("ix_document_acknowledgements_professional_id", "document_acknowledgements", ["professional_id"])

    # --- Table 18: notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", notification_channel, nullable=False, server_default="in_app"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", notification_status, nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_tenant_id", "notifications", ["tenant_id"])
    op.create_index("ix_notifications_recipient_user_id", "notifications", ["recipient_user_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("document_acknowledgements")
    op.execute("ALTER TABLE integrations DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE integrations DROP COLUMN IF EXISTS scopes")
    op.execute("ALTER TABLE integrations DROP COLUMN IF EXISTS credentials_encrypted")
    op.execute("ALTER TABLE integrations DROP COLUMN IF EXISTS health_status")
    op.execute("ALTER TABLE integrations DROP COLUMN IF EXISTS connection_status")
    op.execute("ALTER TABLE integrations DROP COLUMN IF EXISTS auth_type")
    op.execute("ALTER TABLE integrations ALTER COLUMN provider TYPE VARCHAR(100) USING provider::VARCHAR(100)")
    op.execute("DROP TYPE IF EXISTS notification_status")
    op.execute("DROP TYPE IF EXISTS notification_channel")
    op.execute("DROP TYPE IF EXISTS acknowledgement_status")
    # Note: cannot remove enum values 'reassigned'/'CHURNED' without recreating type - left for manual intervention
