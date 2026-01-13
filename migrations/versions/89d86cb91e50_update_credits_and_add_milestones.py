"""update_credits_and_add_milestones

Revision ID: 89d86cb91e50
Revises: 56f128c0ddd9
Create Date: 2026-01-13 20:20:31.452784

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "89d86cb91e50"
down_revision: Union[str, Sequence[str], None] = "56f128c0ddd9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update credits and add milestone bonuses."""
    # Обновление подписки на канал с 2 до 3 кредитов
    op.execute(
        """
        UPDATE bonus_types
        SET credits_amount = 3, updated_at = NOW()
        WHERE code = 'CHANNEL_SUBSCRIPTION';
        """
    )

    # Обновление реферальной регистрации с 5 до 3 кредитов
    op.execute(
        """
        UPDATE bonus_types
        SET credits_amount = 3, updated_at = NOW()
        WHERE code = 'REFERRAL_REGISTRATION';
        """
    )

    # Добавление бонуса за регистрацию
    op.execute(
        """
        INSERT INTO bonus_types (code, name, description, reward_type, credits_amount, ai_credits_amount, is_active, is_repeatable, cooldown_days)
        VALUES ('REGISTRATION', 'Бонус за регистрацию', 'Начисляется один раз при регистрации нового пользователя', 'CREDITS', 3, 0, true, false, null)
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # Добавление майлстоунов для рефералов
    op.execute(
        """
        INSERT INTO bonus_types (code, name, description, reward_type, credits_amount, ai_credits_amount, is_active, is_repeatable, cooldown_days, conditions)
        VALUES
            ('REFERRAL_MILESTONE_5', 'Milestone: 5 рефералов', 'Награда за привлечение 5 рефералов', 'CREDITS', 10, 0, true, false, null, '{"milestone_count": 5}'),
            ('REFERRAL_MILESTONE_10', 'Milestone: 10 рефералов', 'Награда за привлечение 10 рефералов', 'CREDITS', 20, 0, true, false, null, '{"milestone_count": 10}'),
            ('REFERRAL_MILESTONE_25', 'Milestone: 25 рефералов', 'Награда за привлечение 25 рефералов', 'CREDITS', 50, 0, true, false, null, '{"milestone_count": 25}'),
            ('REFERRAL_MILESTONE_50', 'Milestone: 50 рефералов', 'Награда за привлечение 50 рефералов', 'CREDITS', 100, 0, true, false, null, '{"milestone_count": 50}'),
            ('REFERRAL_MILESTONE_100', 'Milestone: 100 рефералов', 'Награда за привлечение 100 рефералов', 'CREDITS', 200, 0, true, false, null, '{"milestone_count": 100}')
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Удаление майлстоунов
    op.execute(
        """
        DELETE FROM bonus_types
        WHERE code IN (
            'REFERRAL_MILESTONE_5',
            'REFERRAL_MILESTONE_10',
            'REFERRAL_MILESTONE_25',
            'REFERRAL_MILESTONE_50',
            'REFERRAL_MILESTONE_100'
        );
        """
    )

    # Удаление бонуса за регистрацию
    op.execute(
        """
        DELETE FROM bonus_types
        WHERE code = 'REGISTRATION';
        """
    )

    # Возврат подписки на канал к 2 кредитам
    op.execute(
        """
        UPDATE bonus_types
        SET credits_amount = 2, updated_at = NOW()
        WHERE code = 'CHANNEL_SUBSCRIPTION';
        """
    )

    # Возврат реферальной регистрации к 5 кредитам
    op.execute(
        """
        UPDATE bonus_types
        SET credits_amount = 5, updated_at = NOW()
        WHERE code = 'REFERRAL_REGISTRATION';
        """
    )
