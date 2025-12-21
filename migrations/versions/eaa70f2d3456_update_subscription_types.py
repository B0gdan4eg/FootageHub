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
    from sqlalchemy import text
    conn = op.get_bind()

    # Проверяем существование старых значений перед переименованием
    try:
        result = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_enum e "
            "JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = 'subscriptiontype' AND e.enumlabel = 'MONTHLY_100')"
        ))
        if result.scalar():
            op.execute("ALTER TYPE subscriptiontype RENAME VALUE 'MONTHLY_100' TO 'MONTHLY_150'")
        else:
            print("Info: MONTHLY_100 already renamed or doesn't exist")
    except Exception as e:
        print(f"Warning: Could not rename MONTHLY_100: {e}")

    try:
        result = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_enum e "
            "JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = 'subscriptiontype' AND e.enumlabel = 'DAILY_20')"
        ))
        if result.scalar():
            op.execute("ALTER TYPE subscriptiontype RENAME VALUE 'DAILY_20' TO 'DAILY_30'")
        else:
            print("Info: DAILY_20 already renamed or doesn't exist")
    except Exception as e:
        print(f"Warning: Could not rename DAILY_20: {e}")


def downgrade() -> None:
    """Downgrade schema."""
    # Откатываем изменения enum типов
    op.execute("ALTER TYPE subscriptiontype RENAME VALUE 'MONTHLY_150' TO 'MONTHLY_100'")
    op.execute("ALTER TYPE subscriptiontype RENAME VALUE 'DAILY_30' TO 'DAILY_20'")
