"""update payments table - remove type add plan_key

Revision ID: e8f6ee98578b
Revises: 539e55ed7fe1
Create Date: 2025-11-25 00:08:04.912657

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f6ee98578b'
down_revision: Union[str, Sequence[str], None] = '539e55ed7fe1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем поле plan_key
    op.add_column('payments', sa.Column('plan_key', sa.String(), nullable=True))

    # Заполняем plan_key значением по умолчанию для существующих записей
    op.execute("UPDATE payments SET plan_key = 'monthly_150' WHERE plan_key IS NULL")

    # Делаем поле обязательным
    op.alter_column('payments', 'plan_key', nullable=False)

    # Удаляем поле type
    op.drop_column('payments', 'type')


def downgrade() -> None:
    """Downgrade schema."""
    # Возвращаем поле type
    op.add_column('payments', sa.Column('type', sa.String(), nullable=True))

    # Заполняем type значением 'subscription'
    op.execute("UPDATE payments SET type = 'subscription'")

    # Удаляем поле plan_key
    op.drop_column('payments', 'plan_key')
