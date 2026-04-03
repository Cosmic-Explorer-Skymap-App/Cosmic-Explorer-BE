"""remove last_ai_query_at column

Revision ID: 24c616c94f85
Revises: e85529e5d551
Create Date: 2026-04-03 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "24c616c94f85"
down_revision: Union[str, None] = "e85529e5d551"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "last_ai_query_at")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_ai_query_at", sa.DateTime(), nullable=True),
    )
