"""Initial migration

Revision ID: b456f1b1c460
Revises:
Create Date: 2025-08-12 23:29:14.364822

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b456f1b1c460"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    from sqlalchemy import text

    conn = op.get_bind()

    # Create UserRole enum
    result = conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole')"))
    if not result.scalar():
        conn.execute(text("CREATE TYPE userrole AS ENUM ('USER', 'ADMIN', 'MANAGER', 'PARTNER')"))

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM(
                "USER", "ADMIN", "MANAGER", "PARTNER", name="userrole", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("credits", sa.Integer(), nullable=True),
        sa.Column("referral_code", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        # Note: ai_credits and ai_credits_used will be added in migration cfc529f762df
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_tg_id"), "users", ["tg_id"], unique=True)

    # Create media table
    op.create_table(
        "media",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )

    # Create payments table
    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("invoice_id", sa.String(), nullable=True),
        sa.Column(
            "type", sa.String(), nullable=True
        ),  # Will be replaced with plan_key in later migration
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_id"),
    )

    # Create downloads table (without subscription_id and service_type initially)
    op.create_table(
        "downloads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("media_id", sa.BigInteger(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(), nullable=True),
        sa.Column("paid", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("downloads")
    op.drop_table("payments")
    op.drop_table("media")
    op.drop_index(op.f("ix_users_tg_id"), table_name="users")
    op.drop_table("users")

    from sqlalchemy import text

    conn = op.get_bind()
    conn.execute(text("DROP TYPE IF EXISTS userrole"))
