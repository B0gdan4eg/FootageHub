"""seed_bonus_types

Revision ID: 56f128c0ddd9
Revises: 0bc41e04ac5f
Create Date: 2025-12-27 20:40:40.355964

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "56f128c0ddd9"
down_revision: Union[str, Sequence[str], None] = "0bc41e04ac5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed initial bonus types."""
    # Создание базовых типов бонусов
    op.execute(
        """
        INSERT INTO bonus_types (code, name, description, reward_type, credits_amount, ai_credits_amount, is_active, is_repeatable, cooldown_days)
        VALUES
        -- Бонус за подписку на канал
        ('CHANNEL_SUBSCRIPTION', 'Бонус за подписку на канал', 'Начисляется при подписке на официальный канал FootageHub', 'CREDITS', 2, 0, true, false, null),

        -- Первый вход
        ('FIRST_LOGIN', 'Приветственный бонус', 'Начисляется при первом входе в бота', 'CREDITS', 3, 0, true, false, null),

        -- Реферальная система
        ('REFERRAL_REGISTRATION', 'Регистрация реферала', 'Бонус когда реферал зарегистрировался и подписался на канал', 'CREDITS', 5, 0, true, true, '{"require_referred_channel_subscription": true}'),

        ('REFERRAL_FIRST_PAYMENT', 'Первая оплата реферала', 'Бонус когда реферал совершил первую покупку', 'CREDITS', 5, 0, true, true, null)
        ON CONFLICT (code) DO NOTHING;
    """
    )


def downgrade() -> None:
    """Remove seeded bonus types."""
    op.execute(
        """
        DELETE FROM bonus_types
        WHERE code IN (
            'CHANNEL_SUBSCRIPTION',
            'FIRST_LOGIN',
            'REFERRAL_REGISTRATION',
            'REFERRAL_FIRST_PAYMENT'
        );
    """
    )
