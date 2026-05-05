"""add per-request pipeline options to job

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-17 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job", sa.Column("segments_to_refine", sa.JSON(), nullable=True))
    op.add_column(
        "job",
        sa.Column(
            "process_code_using_llm",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "job",
        sa.Column(
            "process_figures_using_llm",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("job", "process_figures_using_llm")
    op.drop_column("job", "process_code_using_llm")
    op.drop_column("job", "segments_to_refine")
