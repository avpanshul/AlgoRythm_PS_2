"""normalized_event_versions

Revision ID: 1791300000
Revises: 1791200000
Create Date: 2026-09-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '1791300000'
down_revision: Union[str, Sequence[str], None] = '1791200000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'normalized_event_versions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_id', sa.String(), sa.ForeignKey('normalized_events.event_id'), nullable=False, index=True),
        sa.Column('superseded_by_replay_job_id', sa.Integer(), nullable=True),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('source_ip', sa.String(), nullable=True),
        sa.Column('dest_ip', sa.String(), nullable=True),
        sa.Column('user_name', sa.String(), nullable=True),
        sa.Column('parser_id', sa.String(), nullable=True),
        sa.Column('parser_version', sa.String(), nullable=True),
        sa.Column('mapping_method', sa.String(), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('risk_level', sa.String(), nullable=True),
        sa.Column('normalized_sha256', sa.String(), nullable=True),
        sa.Column('canonical_json', sa.JSON(), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('normalized_event_versions')
