"""sparks

Revision ID: 1791700000
Revises: 1791600000
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '1791700000'
down_revision: Union[str, Sequence[str], None] = '1791600000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sparks',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('entity', sa.String(), nullable=False, index=True),
        sa.Column('trigger_type', sa.String(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('source_incident_id', sa.String(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('path', sa.JSON(), nullable=True),
        sa.Column('hop_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('front', sa.String(), nullable=True),
        sa.Column('proximity_watchlist', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('sparks')
