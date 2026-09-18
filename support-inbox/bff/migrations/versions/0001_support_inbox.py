"""Create application-owned Support Inbox tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001_support_inbox"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS support_inbox")
    op.create_table(
        "support_operators",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="support_inbox",
    )
    op.create_table(
        "support_operator_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "operator_id",
            sa.Uuid(),
            sa.ForeignKey("support_inbox.support_operators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_digest", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("csrf_token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        schema="support_inbox",
    )
    op.create_table(
        "support_operator_audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("operator_id", sa.Uuid(), sa.ForeignKey("support_inbox.support_operators.id")),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(128)),
        sa.Column("target_id", sa.String(256)),
        sa.Column("outcome", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="support_inbox",
    )


def downgrade() -> None:
    op.drop_table("support_operator_audit_log", schema="support_inbox")
    op.drop_table("support_operator_sessions", schema="support_inbox")
    op.drop_table("support_operators", schema="support_inbox")
