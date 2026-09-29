"""merkle_and_drain_cluster

Revision ID: 1790300000
Revises: 1790200000
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1790300000'
down_revision: Union[str, Sequence[str], None] = '1790200000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('dlq_events', sa.Column('drain_cluster_id', sa.String(), nullable=True))
    op.create_index('ix_dlq_events_drain_cluster_id', 'dlq_events', ['drain_cluster_id'])

    op.create_table(
        'merkle_leaves',
        sa.Column('sequence', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('leaf_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_merkle_leaves_event_id', 'merkle_leaves', ['event_id'], unique=True)

    op.create_table(
        'checkpoints',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tree_size', sa.Integer(), nullable=False),
        sa.Column('root_hash', sa.String(), nullable=False),
        sa.Column('signature', sa.String(), nullable=False),
        sa.Column('public_key', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_checkpoints_created_at', 'checkpoints', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_checkpoints_created_at', table_name='checkpoints')
    op.drop_table('checkpoints')
    op.drop_index('ix_merkle_leaves_event_id', table_name='merkle_leaves')
    op.drop_table('merkle_leaves')
    op.drop_index('ix_dlq_events_drain_cluster_id', table_name='dlq_events')
    op.drop_column('dlq_events', 'drain_cluster_id')
