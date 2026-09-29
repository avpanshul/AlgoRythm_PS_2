"""retention_legal_hold

Revision ID: 1791000000
Revises: 1790900000
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1791000000'
down_revision: Union[str, Sequence[str], None] = '1790900000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'retention_policies',
        sa.Column('source_id', sa.String(), sa.ForeignKey('sources.id'), primary_key=True),
        sa.Column('retention_days', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'legal_holds',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('source_id', sa.String(), sa.ForeignKey('sources.id'), nullable=False, index=True),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('released_by', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('legal_holds')
    op.drop_table('retention_policies')
