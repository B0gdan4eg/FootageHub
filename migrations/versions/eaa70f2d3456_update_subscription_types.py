"""update_subscription_types

Revision ID: eaa70f2d3456
Revises: e8f6ee98578b
Create Date: 2025-11-26 00:10:57.710953

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eaa70f2d3456'
down_revision: Union[str, Sequence[str], None] = 'e8f6ee98578b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Обновляем enum типы для subscriptiontype
    op.execute("ALTER TYPE subscriptiontype RENAME VALUE 'MONTHLY_100' TO 'MONTHLY_150'")
    op.execute("ALTER TYPE subscriptiontype RENAME VALUE 'DAILY_20' TO 'DAILY_30'")


def downgrade() -> None:
    """Downgrade schema."""
    # Откатываем изменения enum типов
    op.execute("ALTER TYPE subscriptiontype RENAME VALUE 'MONTHLY_150' TO 'MONTHLY_100'")
    op.execute("ALTER TYPE subscriptiontype RENAME VALUE 'DAILY_30' TO 'DAILY_20'")
