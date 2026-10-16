"""Index the per-user history ordering query.

Revision ID: 0002_history_user_created_at_idx
Revises: 0001_relational_baseline
"""
from alembic import context, op
from sqlalchemy import inspect

revision = "0002_history_user_created_at_idx"
down_revision = "0001_relational_baseline"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_verification_history_user_created_at"


def upgrade():
    if context.is_offline_mode():
        op.create_index(
            INDEX_NAME,
            "verification_history",
            ["user_id", "created_at"],
            unique=False,
        )
        return

    bind = op.get_bind()
    indexes = {
        index["name"]
        for index in inspect(bind).get_indexes("verification_history")
    }
    if INDEX_NAME not in indexes:
        op.create_index(
            INDEX_NAME,
            "verification_history",
            ["user_id", "created_at"],
            unique=False,
        )


def downgrade():
    if context.is_offline_mode():
        op.drop_index(INDEX_NAME, table_name="verification_history")
        return

    bind = op.get_bind()
    indexes = {
        index["name"]
        for index in inspect(bind).get_indexes("verification_history")
    }
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name="verification_history")
