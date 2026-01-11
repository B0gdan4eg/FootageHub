"""add bonus system and ai logs

Revision ID: 0bc41e04ac5f
Revises: cfc529f762df
Create Date: 2025-12-27 20:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0bc41e04ac5f"
down_revision = "cfc529f762df"  # Последняя миграция с ai_credits
branch_labels = None
depends_on = None


def enum_exists(conn, enum_name):
    """Проверка существования ENUM типа"""
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = :name)"), {"name": enum_name}
    )
    return result.scalar()


def upgrade():
    """
    Создание таблиц для бонусной системы и AI логирования.
    """
    conn = op.get_bind()
    inspector = inspect(conn)

    # ==================== BONUS SYSTEM ====================

    # 1. Создаем ENUM типы для бонусной системы (только если не существуют)
    if not enum_exists(conn, "bonusrewardtype"):
        op.execute("CREATE TYPE bonusrewardtype AS ENUM ('CREDITS', 'AI_CREDITS', 'BOTH')")

    if not enum_exists(conn, "bonusstatus"):
        op.execute(
            "CREATE TYPE bonusstatus AS ENUM ('PENDING', 'COMPLETED', 'CANCELLED', 'EXPIRED')"
        )

    if not enum_exists(conn, "referraltriggertype"):
        op.execute(
            "CREATE TYPE referraltriggertype AS ENUM ('REGISTRATION', 'FIRST_PAYMENT', 'SUBSCRIPTION', 'MILESTONE')"
        )

    # 2. Создаем таблицу bonus_types
    if "bonus_types" not in inspector.get_table_names():
        # Создаем таблицу БЕЗ ENUM (с varchar), потом изменим тип
        op.execute(
            """
            CREATE TABLE bonus_types (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(200) NOT NULL,
                description TEXT,

                reward_type bonusrewardtype NOT NULL,
                credits_amount INTEGER DEFAULT 0,
                ai_credits_amount INTEGER DEFAULT 0,

                is_active BOOLEAN DEFAULT true,
                is_repeatable BOOLEAN DEFAULT false,
                cooldown_days INTEGER,
                conditions JSONB,

                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """
        )
        op.create_index("ix_bonus_types_code", "bonus_types", ["code"], unique=True)

    # 3. Создаем таблицу user_bonuses
    if "user_bonuses" not in inspector.get_table_names():
        op.execute(
            """
            CREATE TABLE user_bonuses (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) NOT NULL,
                bonus_type_id INTEGER REFERENCES bonus_types(id) NOT NULL,

                status bonusstatus DEFAULT 'PENDING' NOT NULL,

                credits_granted INTEGER DEFAULT 0,
                ai_credits_granted INTEGER DEFAULT 0,

                metadata JSONB,

                created_at TIMESTAMP DEFAULT now(),
                completed_at TIMESTAMP,
                expires_at TIMESTAMP
            )
        """
        )
        op.create_index("ix_user_bonuses_user_id", "user_bonuses", ["user_id"])
        op.create_index("ix_user_bonuses_status", "user_bonuses", ["status"])

    # 4. Обновляем таблицу referral_rewards - добавляем новые поля
    existing_columns = [col["name"] for col in inspector.get_columns("referral_rewards")]

    if "bonus_id" not in existing_columns:
        op.execute(
            "ALTER TABLE referral_rewards ADD COLUMN bonus_id INTEGER REFERENCES user_bonuses(id)"
        )

    if "trigger_type" not in existing_columns:
        op.execute("ALTER TABLE referral_rewards ADD COLUMN trigger_type referraltriggertype")

    if "trigger_metadata" not in existing_columns:
        op.execute("ALTER TABLE referral_rewards ADD COLUMN trigger_metadata JSONB")

    if "completed_at" not in existing_columns:
        op.execute("ALTER TABLE referral_rewards ADD COLUMN completed_at TIMESTAMP")

    # ==================== AI GENERATION LOGS ====================

    # 5. Создаем ENUM типы для AI логов (только если не существуют)
    if not enum_exists(conn, "aigenerationstatus"):
        op.execute(
            "CREATE TYPE aigenerationstatus AS ENUM ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED')"
        )

    if not enum_exists(conn, "aigenerationtype"):
        op.execute("CREATE TYPE aigenerationtype AS ENUM ('IMAGE', 'VIDEO', 'IMAGE_TO_VIDEO')")

    # 6. Создаем таблицу ai_generation_logs
    if "ai_generation_logs" not in inspector.get_table_names():
        op.execute(
            """
            CREATE TABLE ai_generation_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) NOT NULL,

                provider VARCHAR(50) NOT NULL,
                model VARCHAR(100) NOT NULL,
                generation_type aigenerationtype NOT NULL,

                prompt TEXT NOT NULL,
                parameters JSONB,

                status aigenerationstatus DEFAULT 'PENDING' NOT NULL,
                result_url VARCHAR(500),
                error_message TEXT,

                ai_credits_spent INTEGER DEFAULT 1,
                processing_time_seconds INTEGER,

                created_at TIMESTAMP DEFAULT now(),
                completed_at TIMESTAMP
            )
        """
        )
        op.create_index("ix_ai_generation_logs_user_id", "ai_generation_logs", ["user_id"])
        op.create_index("ix_ai_generation_logs_status", "ai_generation_logs", ["status"])
        op.create_index("ix_ai_generation_logs_created_at", "ai_generation_logs", ["created_at"])


def downgrade():
    """
    Откат миграции - удаление таблиц и ENUM типов.
    """
    # Удаляем таблицы
    op.drop_table("ai_generation_logs")
    op.drop_table("user_bonuses")
    op.drop_table("bonus_types")

    # Удаляем добавленные колонки из referral_rewards
    op.drop_column("referral_rewards", "completed_at")
    op.drop_column("referral_rewards", "trigger_metadata")
    op.drop_column("referral_rewards", "trigger_type")
    op.drop_column("referral_rewards", "bonus_id")

    # Удаляем ENUM типы
    sa.Enum(name="aigenerationtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="aigenerationstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="referraltriggertype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="bonusstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="bonusrewardtype").drop(op.get_bind(), checkfirst=True)
