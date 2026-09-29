"""checkpoint_witness_rfc3161_reverify

Revision ID: 1791600000
Revises: 1791500000
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '1791600000'
down_revision: Union[str, Sequence[str], None] = '1791500000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('checkpoints', sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('checkpoints', sa.Column('last_verification_status', sa.String(), nullable=True))
    op.add_column('checkpoints', sa.Column('last_verification_detail', sa.Text(), nullable=True))

    op.add_column('checkpoints', sa.Column('witness_signature', sa.String(), nullable=True))
    op.add_column('checkpoints', sa.Column('witness_public_key', sa.String(), nullable=True))
    op.add_column('checkpoints', sa.Column('witness_algorithm', sa.String(), nullable=True))
    op.add_column('checkpoints', sa.Column('witness_source', sa.String(), nullable=True))
    op.add_column('checkpoints', sa.Column('witnessed_at', sa.DateTime(timezone=True), nullable=True))

    op.add_column('checkpoints', sa.Column('rfc3161_status', sa.String(), nullable=True, server_default='not_configured'))
    op.add_column('checkpoints', sa.Column('rfc3161_token_b64', sa.Text(), nullable=True))
    op.add_column('checkpoints', sa.Column('rfc3161_tsa_url', sa.String(), nullable=True))


def downgrade() -> None:
    for col in [
        'rfc3161_tsa_url', 'rfc3161_token_b64', 'rfc3161_status',
        'witnessed_at', 'witness_source', 'witness_algorithm', 'witness_public_key', 'witness_signature',
        'last_verification_detail', 'last_verification_status', 'last_verified_at',
    ]:
        op.drop_column('checkpoints', col)
