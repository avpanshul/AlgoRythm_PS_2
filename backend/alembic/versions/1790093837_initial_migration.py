"""Initial migration

Revision ID: 1790093837
Revises: 
Create Date: 2026-09-22 21:39:47.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1790093837'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # sources
    op.create_table('sources',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('vendor', sa.String(), nullable=True),
    sa.Column('product', sa.String(), nullable=True),
    sa.Column('device_type', sa.String(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sources_id'), 'sources', ['id'], unique=False)

    # raw_event_metadata
    op.create_table('raw_event_metadata',
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('source_id', sa.String(), nullable=True),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('ingestion_protocol', sa.String(), nullable=False),
    sa.Column('raw_sha256', sa.String(), nullable=False),
    sa.Column('raw_location', sa.String(), nullable=False),
    sa.Column('processing_status', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
    sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index(op.f('ix_raw_event_metadata_event_id'), 'raw_event_metadata', ['event_id'], unique=False)
    op.create_index(op.f('ix_raw_event_metadata_raw_sha256'), 'raw_event_metadata', ['raw_sha256'], unique=False)

    # mapping_registry
    op.create_table('mapping_registry',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('vendor', sa.String(), nullable=False),
    sa.Column('device_type', sa.String(), nullable=True),
    sa.Column('raw_field', sa.String(), nullable=False),
    sa.Column('canonical_field', sa.String(), nullable=False),
    sa.Column('mapping_type', sa.String(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('approved', sa.Boolean(), nullable=True),
    sa.Column('approved_by', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mapping_registry_id'), 'mapping_registry', ['id'], unique=False)
    op.create_index(op.f('ix_mapping_registry_vendor'), 'mapping_registry', ['vendor'], unique=False)
    op.create_index(op.f('ix_mapping_registry_device_type'), 'mapping_registry', ['device_type'], unique=False)
    op.create_index(op.f('ix_mapping_registry_raw_field'), 'mapping_registry', ['raw_field'], unique=False)

    # unknown_templates
    op.create_table('unknown_templates',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('cluster_id', sa.String(), nullable=False),
    sa.Column('template_str', sa.String(), nullable=False),
    sa.Column('vendor', sa.String(), nullable=True),
    sa.Column('event_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_unknown_templates_id'), 'unknown_templates', ['id'], unique=False)
    op.create_index(op.f('ix_unknown_templates_cluster_id'), 'unknown_templates', ['cluster_id'], unique=False)

    # audit_logs
    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user', sa.String(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('entity_type', sa.String(), nullable=False),
    sa.Column('entity_id', sa.String(), nullable=False),
    sa.Column('before_state', sa.JSON(), nullable=True),
    sa.Column('after_state', sa.JSON(), nullable=True),
    sa.Column('reason', sa.String(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_unknown_templates_cluster_id'), table_name='unknown_templates')
    op.drop_index(op.f('ix_unknown_templates_id'), table_name='unknown_templates')
    op.drop_table('unknown_templates')
    op.drop_index(op.f('ix_mapping_registry_raw_field'), table_name='mapping_registry')
    op.drop_index(op.f('ix_mapping_registry_device_type'), table_name='mapping_registry')
    op.drop_index(op.f('ix_mapping_registry_vendor'), table_name='mapping_registry')
    op.drop_index(op.f('ix_mapping_registry_id'), table_name='mapping_registry')
    op.drop_table('mapping_registry')
    op.drop_index(op.f('ix_raw_event_metadata_raw_sha256'), table_name='raw_event_metadata')
    op.drop_index(op.f('ix_raw_event_metadata_event_id'), table_name='raw_event_metadata')
    op.drop_table('raw_event_metadata')
    op.drop_index(op.f('ix_sources_id'), table_name='sources')
    op.drop_table('sources')
