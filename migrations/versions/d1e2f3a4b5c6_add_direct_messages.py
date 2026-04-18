"""add direct messages

Revision ID: d1e2f3a4b5c6
Revises: c9d4e5f6a7b8
Create Date: 2026-04-06 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c9d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    existing_tables = set(inspector.get_table_names())

    if "conversations" not in existing_tables:
        op.create_table(
            "conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user1_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user2_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("unread_count_1", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unread_count_2", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("user1_id", "user2_id", name="uq_conversation"),
        )

    conversation_indexes = {index["name"] for index in inspector.get_indexes("conversations")} if "conversations" in existing_tables else set()
    if "ix_conversations_user1_id" not in conversation_indexes:
        op.create_index("ix_conversations_user1_id", "conversations", ["user1_id"])
    if "ix_conversations_user2_id" not in conversation_indexes:
        op.create_index("ix_conversations_user2_id", "conversations", ["user2_id"])

    if "messages" not in existing_tables:
        op.create_table(
            "messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )

    message_indexes = {index["name"] for index in inspector.get_indexes("messages")} if "messages" in existing_tables else set()
    if "messages" not in existing_tables or "ix_messages_conversation_id" not in message_indexes:
        op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    if "messages" not in existing_tables or "ix_messages_sender_id" not in message_indexes:
        op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
    if "messages" not in existing_tables or "ix_messages_created_at" not in message_indexes:
        op.create_index("ix_messages_created_at", "messages", ["created_at"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
