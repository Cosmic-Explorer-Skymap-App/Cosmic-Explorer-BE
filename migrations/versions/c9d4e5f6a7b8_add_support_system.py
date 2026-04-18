"""add support system and admin flag

Revision ID: c9d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-05 12:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    # Add is_admin to users
    user_columns = {column['name'] for column in inspector.get_columns('users')}
    if 'is_admin' not in user_columns:
        op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=True, server_default='false'))
        op.execute("UPDATE users SET is_admin = false WHERE is_admin IS NULL")
        op.alter_column('users', 'is_admin', nullable=False, server_default='false')

    # Create support_messages
    if 'support_messages' not in inspector.get_table_names():
        op.create_table(
            'support_messages',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('full_name', sa.String(length=100), nullable=False),
            sa.Column('email', sa.String(), nullable=False),
            sa.Column('subject', sa.String(length=200), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('image_url', sa.String(), nullable=True),
            sa.Column('status', sa.String(length=20), server_default='open', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_support_messages_id', 'support_messages', ['id'])


def downgrade() -> None:
    op.drop_index('ix_support_messages_id', table_name='support_messages')
    op.drop_table('support_messages')
    op.drop_column('users', 'is_admin')
