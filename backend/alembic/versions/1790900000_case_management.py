"""case_management

Revision ID: 1790900000
Revises: 1790800000
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1790900000'
down_revision: Union[str, Sequence[str], None] = '1790800000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cases',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('correlation_id', sa.String(), sa.ForeignKey('correlated_incidents.id'), nullable=True, index=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False, server_default='medium'),
        sa.Column('status', sa.String(), nullable=False, server_default='open'),
        sa.Column('owner', sa.String(), nullable=True),
        sa.Column('notes', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_cases_severity', 'cases', ['severity'])
    op.create_index('ix_cases_status', 'cases', ['status'])

    op.create_table(
        'oncall_contacts',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('escalation_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_oncall_contacts_escalation_order', 'oncall_contacts', ['escalation_order'])

    op.create_table(
        'notifications',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('case_id', sa.String(), sa.ForeignKey('cases.id'), nullable=False, index=True),
        sa.Column('contact_id', sa.String(), sa.ForeignKey('oncall_contacts.id'), nullable=True),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('dedup_key', sa.String(), nullable=False, index=True),
        sa.Column('status', sa.String(), nullable=False, server_default='sent'),
        sa.Column('detail', sa.String(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(), nullable=True),
        sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # No explicit op.create_index('ix_notifications_dedup_key', ...) here --
    # the `dedup_key` column above already declares `index=True`, which
    # makes op.create_table() create that exact index itself. The explicit
    # call used to duplicate it, causing a real
    # `psycopg2.errors.DuplicateTable: relation "ix_notifications_dedup_key"
    # already exists` on PostgreSQL -- invisible until this migration was
    # run against a real Postgres for the first time (every prior test used
    # SQLite's Base.metadata.create_all(), which never goes through Alembic
    # at all), found running the real E10 kind smoke test.


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_index('ix_oncall_contacts_escalation_order', table_name='oncall_contacts')
    op.drop_table('oncall_contacts')
    op.drop_index('ix_cases_status', table_name='cases')
    op.drop_index('ix_cases_severity', table_name='cases')
    op.drop_table('cases')
