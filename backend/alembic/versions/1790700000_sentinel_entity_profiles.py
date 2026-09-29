"""sentinel_entity_profiles

Revision ID: 1790700000
Revises: 1790600000
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1790700000'
down_revision: Union[str, Sequence[str], None] = '1790600000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('normalized_events', sa.Column('sentinel_processed_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        'entity_profiles',
        sa.Column('entity_id', sa.String(), primary_key=True, index=True),
        sa.Column('entity_type', sa.String(), nullable=False, server_default='ip'),
        sa.Column('known_dest_ports', sa.JSON(), nullable=True),
        sa.Column('known_protocols', sa.JSON(), nullable=True),
        sa.Column('known_peers', sa.JSON(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('reason_log', sa.JSON(), nullable=True),
        sa.Column('event_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_entity_profiles_risk_score', 'entity_profiles', ['risk_score'])


def downgrade() -> None:
    op.drop_index('ix_entity_profiles_risk_score', table_name='entity_profiles')
    op.drop_table('entity_profiles')
    op.drop_column('normalized_events', 'sentinel_processed_at')
