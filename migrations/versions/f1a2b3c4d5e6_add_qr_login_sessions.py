"""add qr_login_sessions for Telegram QR login

Revision ID: f1a2b3c4d5e6
Revises: a1b2c3d4e5f6
Create Date: 2026-05-30 13:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

# Тип создаём вручную (идемпотентно) в upgrade(), поэтому create_type=False —
# чтобы create_table НЕ пытался создать enum повторно (иначе DuplicateObjectError).
qr_login_status = postgresql.ENUM(
    "PENDING",
    "CONFIRMED",
    "REJECTED",
    "EXPIRED",
    name="qr_login_status",
    create_type=False,
)


def upgrade():
    # Идемпотентное создание enum-типа (безопасно при повторном/частичном прогоне)
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE qr_login_status AS ENUM ('PENDING', 'CONFIRMED', 'REJECTED', 'EXPIRED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )

    op.create_table(
        "qr_login_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("status", qr_login_status, nullable=False, server_default="PENDING"),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qr_login_sessions_token", "qr_login_sessions", ["token"], unique=True)


def downgrade():
    op.drop_index("ix_qr_login_sessions_token", table_name="qr_login_sessions")
    op.drop_table("qr_login_sessions")
    op.execute("DROP TYPE IF EXISTS qr_login_status")
