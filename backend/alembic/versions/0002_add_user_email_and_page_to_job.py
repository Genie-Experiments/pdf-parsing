"""add user_email and page to job

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-17 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user_email — backfill existing rows with a placeholder so NOT NULL can be enforced
    op.add_column("job", sa.Column("user_email", sa.String(), nullable=True))
    op.execute(
        "UPDATE job SET user_email = 'migrated@unknown' WHERE user_email IS NULL"
    )
    op.alter_column("job", "user_email", nullable=False)
    op.create_index("ix_job_user_email", "job", ["user_email"])

    # page — nullable, None means full PDF
    op.add_column("job", sa.Column("page", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_index("ix_job_user_email", table_name="job")
    op.drop_column("job", "user_email")
    op.drop_column("job", "page")
