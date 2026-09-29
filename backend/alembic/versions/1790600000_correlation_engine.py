"""correlation_engine

Revision ID: 1790600000
Revises: 1790500000
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1790600000'
down_revision: Union[str, Sequence[str], None] = '1790500000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('normalized_events', sa.Column('correlation_id', sa.String(), nullable=True))
    op.create_index('ix_normalized_events_correlation_id', 'normalized_events', ['correlation_id'])

    op.create_table(
        'correlated_incidents',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('rule_id', sa.String(), nullable=False, index=True),
        sa.Column('rule_name', sa.String(), nullable=False),
        sa.Column('correlate_key', sa.String(), nullable=False, index=True),
        sa.Column('event_ids', sa.JSON(), nullable=False),
        sa.Column('distinct_source_count', sa.Integer(), nullable=False),
        sa.Column('stage_summary', sa.JSON(), nullable=True),
        sa.Column('first_event_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='open'),
        sa.Column('owner', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_correlated_incidents_status', 'correlated_incidents', ['status'])


def downgrade() -> None:
    op.drop_index('ix_correlated_incidents_status', table_name='correlated_incidents')
    op.drop_table('correlated_incidents')
    op.drop_index('ix_normalized_events_correlation_id', table_name='normalized_events')
    op.drop_column('normalized_events', 'correlation_id')
