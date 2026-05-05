"""add cancelled to jobstatus enum

Revision ID: 0005
Revises: 0004
Create Date: 2025-01-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres supports adding enum values but not removing them.
    # IF NOT EXISTS prevents failure on re-runs.
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # Postgres does not support removing enum values without recreating the type.
    # Leave the value in place to avoid breaking live data.
    pass
