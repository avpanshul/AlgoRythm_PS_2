"""source_fingerprint

Revision ID: 1791200000
Revises: 1791100000
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1791200000'
down_revision: Union[str, Sequence[str], None] = '1791100000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'source_fingerprints',
        sa.Column('source_id', sa.String(), sa.ForeignKey('sources.id'), primary_key=True),
        sa.Column('field_names', sa.JSON(), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=False),
        sa.Column('drift_detected', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('drift_detail', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_source_fingerprints_drift_detected', 'source_fingerprints', ['drift_detected'])


def downgrade() -> None:
    op.drop_index('ix_source_fingerprints_drift_detected', table_name='source_fingerprints')
    op.drop_table('source_fingerprints')
