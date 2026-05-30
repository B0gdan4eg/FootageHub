"""add qr_login_sessions for Telegram QR login

Revision ID: f1a2b3c4d5e6
Revises: a1b2c3d4e5f6
Create Date: 2026-05-30 13:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # Enum статуса QR-сессии входа
    op.execute(
        "CREATE TYPE qr_login_status AS ENUM ('PENDING', 'CONFIRMED', 'REJECTED', 'EXPIRED')"
    )

    op.create_table(
        "qr_login_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "CONFIRMED",
                "REJECTED",
                "EXPIRED",
                name="qr_login_status",
            ),
            nullable=False,
            server_default="PENDING",
        ),
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
