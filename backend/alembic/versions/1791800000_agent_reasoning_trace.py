"""agent_reasoning_trace

Revision ID: 1791800000
Revises: 1791700000
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '1791800000'
down_revision: Union[str, Sequence[str], None] = '1791700000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_reasoning_trace',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('cluster_id', sa.String(), nullable=False, index=True),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('feedback_used', sa.Text(), nullable=True),
        sa.Column('field_classifications', sa.JSON(), nullable=False),
        sa.Column('mapped_field_count', sa.Integer(), nullable=False),
        sa.Column('unmapped_field_count', sa.Integer(), nullable=False),
        sa.Column('fixture_avg_mapped_per_sample', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('agent_reasoning_trace')
