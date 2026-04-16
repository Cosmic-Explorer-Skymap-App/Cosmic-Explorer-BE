"""add non-negative check constraints on counter columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-05 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user_profiles counters
    op.create_check_constraint(
        "ck_user_profiles_follower_count_nn",
        "user_profiles",
        "follower_count >= 0",
    )
    op.create_check_constraint(
        "ck_user_profiles_following_count_nn",
        "user_profiles",
        "following_count >= 0",
    )
    op.create_check_constraint(
        "ck_user_profiles_post_count_nn",
        "user_profiles",
        "post_count >= 0",
    )
    # posts counters
    op.create_check_constraint(
        "ck_posts_like_count_nn",
        "posts",
        "like_count >= 0",
    )
    op.create_check_constraint(
        "ck_posts_comment_count_nn",
        "posts",
        "comment_count >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_posts_comment_count_nn", "posts", type_="check")
    op.drop_constraint("ck_posts_like_count_nn", "posts", type_="check")
    op.drop_constraint("ck_user_profiles_post_count_nn", "user_profiles", type_="check")
    op.drop_constraint("ck_user_profiles_following_count_nn", "user_profiles", type_="check")
    op.drop_constraint("ck_user_profiles_follower_count_nn", "user_profiles", type_="check")
