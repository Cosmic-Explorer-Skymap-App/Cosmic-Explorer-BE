"""add admin permission assignments

Revision ID: a7f4d9c2e1b0
Revises: f6a7b8c9d0e1
Create Date: 2026-04-18 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7f4d9c2e1b0"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "admin_accounts" not in existing_tables:
        op.create_table(
            "admin_accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(length=80), nullable=False, unique=True),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("display_name", sa.String(length=120), nullable=True),
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("is_founder", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by_admin_id", sa.Integer(), sa.ForeignKey("admin_accounts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_admin_accounts_username", "admin_accounts", ["username"])

    if "admin_permission_assignments" not in existing_tables:
        op.create_table(
            "admin_permission_assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("admin_account_id", sa.Integer(), sa.ForeignKey("admin_accounts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("permission", sa.String(length=40), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("admin_account_id", "permission", name="uq_admin_permission_assignment"),
        )
        op.create_index("ix_admin_permission_assignments_id", "admin_permission_assignments", ["id"])
        op.create_index("ix_admin_permission_assignments_admin_account_id", "admin_permission_assignments", ["admin_account_id"])
        op.create_index("ix_admin_permission_assignments_permission", "admin_permission_assignments", ["permission"])


def downgrade() -> None:
    op.drop_index("ix_admin_accounts_username", table_name="admin_accounts")
    op.drop_table("admin_accounts")

    op.drop_index("ix_admin_permission_assignments_permission", table_name="admin_permission_assignments")
    op.drop_index("ix_admin_permission_assignments_admin_account_id", table_name="admin_permission_assignments")
    op.drop_index("ix_admin_permission_assignments_id", table_name="admin_permission_assignments")
    op.drop_table("admin_permission_assignments")
