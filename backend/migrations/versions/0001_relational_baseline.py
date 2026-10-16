"""Create the current users and verification history schema.

Revision ID: 0001_relational_baseline
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_relational_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"], unique=False)

    op.create_table(
        "verification_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("diagnosis_hint", sa.String(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("violation_count", sa.Integer(), nullable=True),
        sa.Column("highest_severity", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_verification_history_id",
        "verification_history",
        ["id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_verification_history_id", table_name="verification_history")
    op.drop_table("verification_history")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
