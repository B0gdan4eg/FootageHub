"""add qr_login_sessions for Telegram QR login

Revision ID: f1a2b3c4d5e6
Revises: a1b2c3d4e5f6
Create Date: 2026-05-30 13:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # Полностью идемпотентно: безопасно при повторном/частичном прогоне.
    # На проде тип/таблица могли остаться от прошлой неудачной миграции,
    # при этом alembic_version не успел записаться — поэтому используем
    # нативные IF NOT EXISTS и DO-блок, чтобы повтор просто записал ревизию.
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE qr_login_status AS ENUM ('PENDING', 'CONFIRMED', 'REJECTED', 'EXPIRED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS qr_login_sessions (
            id SERIAL PRIMARY KEY,
            token VARCHAR(64) NOT NULL,
            status qr_login_status NOT NULL DEFAULT 'PENDING',
            user_id BIGINT REFERENCES users (id) ON DELETE CASCADE,
            expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            confirmed_at TIMESTAMP WITHOUT TIME ZONE
        );
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_qr_login_sessions_token "
        "ON qr_login_sessions (token);"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_qr_login_sessions_token;")
    op.execute("DROP TABLE IF EXISTS qr_login_sessions;")
    op.execute("DROP TYPE IF EXISTS qr_login_status;")
