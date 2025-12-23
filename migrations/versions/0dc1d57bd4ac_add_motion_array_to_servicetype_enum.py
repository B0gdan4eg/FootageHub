"""Add MOTION_ARRAY to ServiceType enum

Revision ID: 0dc1d57bd4ac
Revises: eaa70f2d3456
Create Date: 2025-12-23 23:13:17.087084

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0dc1d57bd4ac'
down_revision: Union[str, Sequence[str], None] = 'eaa70f2d3456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add 'MOTION_ARRAY' to the servicetype enum (uppercase to match ENVATO, FREEPIK, ALL)
    op.execute("ALTER TYPE servicetype ADD VALUE IF NOT EXISTS 'MOTION_ARRAY'")


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL doesn't support removing enum values easily
    # You would need to recreate the enum type and update all tables
    pass
