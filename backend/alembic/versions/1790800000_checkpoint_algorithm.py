"""checkpoint_algorithm

Revision ID: 1790800000
Revises: 1790700000
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1790800000'
down_revision: Union[str, Sequence[str], None] = '1790700000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('checkpoints', sa.Column('algorithm', sa.String(), nullable=True, server_default='ed25519'))


def downgrade() -> None:
    op.drop_column('checkpoints', 'algorithm')
