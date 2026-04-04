"""add web auth: phone_number, sms_verifications, bot_link_requests

Revision ID: a1b2c3d4e5f6
Revises: 89d86cb91e50
Create Date: 2026-03-17 12:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "89d86cb91e50"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Сделать tg_id nullable (web-пользователи без Telegram)
    op.alter_column("users", "tg_id", nullable=True)

    # 2. Добавить phone_number в таблицу users
    op.add_column(
        "users",
        sa.Column("phone_number", sa.String(20), nullable=True),
    )
    op.create_unique_constraint("uq_users_phone_number", "users", ["phone_number"])
    op.create_index("ix_users_phone_number", "users", ["phone_number"])

    # 3. Создать таблицу sms_verifications
    op.create_table(
        "sms_verifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sms_verifications_phone", "sms_verifications", ["phone"])

    # 4. Создать enum для статуса запроса привязки
    op.execute(
        "CREATE TYPE link_request_status AS ENUM ('PENDING', 'CONFIRMED', 'REJECTED', 'EXPIRED')"
    )

    # 5. Создать таблицу bot_link_requests
    op.create_table(
        "bot_link_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("web_user_id", sa.BigInteger(), nullable=False),
        sa.Column("bot_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "CONFIRMED",
                "REJECTED",
                "EXPIRED",
                name="link_request_status",
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["web_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bot_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("bot_link_requests")
    op.execute("DROP TYPE IF EXISTS link_request_status")
    op.drop_index("ix_sms_verifications_phone", table_name="sms_verifications")
    op.drop_table("sms_verifications")
    op.drop_index("ix_users_phone_number", table_name="users")
    op.drop_constraint("uq_users_phone_number", "users", type_="unique")
    op.drop_column("users", "phone_number")
    op.alter_column("users", "tg_id", nullable=False)
