"""audit_log_hash_chain

Revision ID: 1790500000
Revises: 1790400000
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1790500000'
down_revision: Union[str, Sequence[str], None] = '1790400000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('prev_hash', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('hash', sa.String(), nullable=True))
    # Existing rows (if any) predate the hash chain and cannot be retroactively
    # chained without their original insertion-time field values being
    # re-hashed in strict order -- acceptable for a column that didn't exist
    # before. New rows from this migration forward are chained by the
    # before_insert listener in app/models/all.py.


def downgrade() -> None:
    op.drop_column('audit_logs', 'hash')
    op.drop_column('audit_logs', 'prev_hash')
