"""parser_coverage_status

Revision ID: 1790400000
Revises: 1790300000
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1790400000'
down_revision: Union[str, Sequence[str], None] = '1790300000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('parsers', sa.Column('coverage_status', sa.String(), nullable=False, server_default='fixture'))
    op.create_index('ix_parsers_coverage_status', 'parsers', ['coverage_status'])


def downgrade() -> None:
    op.drop_index('ix_parsers_coverage_status', table_name='parsers')
    op.drop_column('parsers', 'coverage_status')
