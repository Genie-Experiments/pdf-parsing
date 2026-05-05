"""add user_quota table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-17 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_quota",
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("page_quota", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("pages_used", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("email"),
    )


def downgrade() -> None:
    op.drop_table("user_quota")
