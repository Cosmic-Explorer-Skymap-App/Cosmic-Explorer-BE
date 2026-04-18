"""add admin control center tables

Revision ID: f6a7b8c9d0e1
Revises: d1e2f3a4b5c6
Create Date: 2026-04-15 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "user_devices" not in existing_tables:
        op.create_table(
            "user_devices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String(length=20), nullable=False),
            sa.Column("app_version", sa.String(length=50), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("user_id", "platform", name="uq_user_device_platform"),
        )
        op.create_index("ix_user_devices_id", "user_devices", ["id"])
        op.create_index("ix_user_devices_user_id", "user_devices", ["user_id"])
        op.create_index("ix_user_devices_platform", "user_devices", ["platform"])
        op.create_index("ix_user_devices_last_seen_at", "user_devices", ["last_seen_at"])

    if "social_connections" not in existing_tables:
        op.create_table(
            "social_connections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("platform", sa.String(length=20), nullable=False),
            sa.Column("account_name", sa.String(length=150), nullable=False),
            sa.Column("account_id", sa.String(length=150), nullable=True),
            sa.Column("access_token", sa.String(length=500), nullable=True),
            sa.Column("refresh_token", sa.String(length=500), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("platform", "account_name", name="uq_social_connection_platform_account"),
        )
        op.create_index("ix_social_connections_id", "social_connections", ["id"])
        op.create_index("ix_social_connections_platform", "social_connections", ["platform"])

    if "social_contents" not in existing_tables:
        op.create_table(
            "social_contents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("platform", sa.String(length=20), nullable=False),
            sa.Column("connection_id", sa.Integer(), sa.ForeignKey("social_connections.id", ondelete="SET NULL"), nullable=True),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("media_url", sa.String(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("impressions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("conversions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("spend", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_social_contents_id", "social_contents", ["id"])
        op.create_index("ix_social_contents_platform", "social_contents", ["platform"])
        op.create_index("ix_social_contents_status", "social_contents", ["status"])
        op.create_index("ix_social_contents_created_at", "social_contents", ["created_at"])

    if "bug_reports" not in existing_tables:
        op.create_table(
            "bug_reports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source_platform", sa.String(length=20), nullable=False, server_default="unknown"),
            sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_bug_reports_id", "bug_reports", ["id"])
        op.create_index("ix_bug_reports_user_id", "bug_reports", ["user_id"])
        op.create_index("ix_bug_reports_source_platform", "bug_reports", ["source_platform"])
        op.create_index("ix_bug_reports_severity", "bug_reports", ["severity"])
        op.create_index("ix_bug_reports_status", "bug_reports", ["status"])
        op.create_index("ix_bug_reports_created_at", "bug_reports", ["created_at"])

    if "email_campaigns" not in existing_tables:
        op.create_table(
            "email_campaigns",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("target_platform", sa.String(length=20), nullable=True),
            sa.Column("target_tier", sa.String(length=20), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
            sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_email_campaigns_id", "email_campaigns", ["id"])
        op.create_index("ix_email_campaigns_target_platform", "email_campaigns", ["target_platform"])
        op.create_index("ix_email_campaigns_target_tier", "email_campaigns", ["target_tier"])
        op.create_index("ix_email_campaigns_status", "email_campaigns", ["status"])
        op.create_index("ix_email_campaigns_created_at", "email_campaigns", ["created_at"])

    if "finance_entries" not in existing_tables:
        op.create_table(
            "finance_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("entry_type", sa.String(length=20), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_finance_entries_id", "finance_entries", ["id"])
        op.create_index("ix_finance_entries_entry_type", "finance_entries", ["entry_type"])
        op.create_index("ix_finance_entries_category", "finance_entries", ["category"])
        op.create_index("ix_finance_entries_occurred_at", "finance_entries", ["occurred_at"])
        op.create_index("ix_finance_entries_created_at", "finance_entries", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_finance_entries_created_at", table_name="finance_entries")
    op.drop_index("ix_finance_entries_occurred_at", table_name="finance_entries")
    op.drop_index("ix_finance_entries_category", table_name="finance_entries")
    op.drop_index("ix_finance_entries_entry_type", table_name="finance_entries")
    op.drop_index("ix_finance_entries_id", table_name="finance_entries")
    op.drop_table("finance_entries")

    op.drop_index("ix_email_campaigns_created_at", table_name="email_campaigns")
    op.drop_index("ix_email_campaigns_status", table_name="email_campaigns")
    op.drop_index("ix_email_campaigns_target_tier", table_name="email_campaigns")
    op.drop_index("ix_email_campaigns_target_platform", table_name="email_campaigns")
    op.drop_index("ix_email_campaigns_id", table_name="email_campaigns")
    op.drop_table("email_campaigns")

    op.drop_index("ix_bug_reports_created_at", table_name="bug_reports")
    op.drop_index("ix_bug_reports_status", table_name="bug_reports")
    op.drop_index("ix_bug_reports_severity", table_name="bug_reports")
    op.drop_index("ix_bug_reports_source_platform", table_name="bug_reports")
    op.drop_index("ix_bug_reports_user_id", table_name="bug_reports")
    op.drop_index("ix_bug_reports_id", table_name="bug_reports")
    op.drop_table("bug_reports")

    op.drop_index("ix_social_contents_created_at", table_name="social_contents")
    op.drop_index("ix_social_contents_status", table_name="social_contents")
    op.drop_index("ix_social_contents_platform", table_name="social_contents")
    op.drop_index("ix_social_contents_id", table_name="social_contents")
    op.drop_table("social_contents")

    op.drop_index("ix_social_connections_platform", table_name="social_connections")
    op.drop_index("ix_social_connections_id", table_name="social_connections")
    op.drop_table("social_connections")

    op.drop_index("ix_user_devices_last_seen_at", table_name="user_devices")
    op.drop_index("ix_user_devices_platform", table_name="user_devices")
    op.drop_index("ix_user_devices_user_id", table_name="user_devices")
    op.drop_index("ix_user_devices_id", table_name="user_devices")
    op.drop_table("user_devices")
