"""add_monthly_50_and_monthly_400_subscription_types

Revision ID: 42d1a229ebd0
Revises: 0dc1d57bd4ac
Create Date: 2025-12-24 00:09:49.992530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42d1a229ebd0'
down_revision: Union[str, Sequence[str], None] = '0dc1d57bd4ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add 'monthly_50' and 'monthly_400' to the subscriptiontype enum
    op.execute("ALTER TYPE subscriptiontype ADD VALUE IF NOT EXISTS 'monthly_50'")
    op.execute("ALTER TYPE subscriptiontype ADD VALUE IF NOT EXISTS 'monthly_400'")


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL doesn't support removing enum values easily
    # You would need to recreate the enum type and update all tables
    pass
