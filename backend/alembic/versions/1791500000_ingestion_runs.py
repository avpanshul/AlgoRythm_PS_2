"""ingestion_runs

Revision ID: 1791500000
Revises: 1791400000
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '1791500000'
down_revision: Union[str, Sequence[str], None] = '1791400000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ingestion_runs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('trigger', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('new_events_ingested', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped_duplicates', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('dlq_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('format_breakdown', sa.JSON(), nullable=True),
        sa.Column('corpus_exhausted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('error_message', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('ingestion_runs')
