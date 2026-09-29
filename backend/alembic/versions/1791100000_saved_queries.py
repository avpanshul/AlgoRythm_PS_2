"""saved_queries

Revision ID: 1791100000
Revises: 1791000000
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1791100000'
down_revision: Union[str, Sequence[str], None] = '1791000000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'saved_queries',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('filter', sa.JSON(), nullable=False),
        sa.Column('owner', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('saved_queries')
