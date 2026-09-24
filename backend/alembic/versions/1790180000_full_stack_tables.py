"""full_stack_tables

Revision ID: 1790180000
Revises: 1790093837
Create Date: 2026-09-23 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1790180000'
down_revision: Union[str, Sequence[str], None] = '1790093837'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # normalized_events
    op.create_table('normalized_events',
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('source_id', sa.String(), nullable=True),
    sa.Column('event_data', sa.JSON(), nullable=True),
    sa.Column('source_ip', sa.String(), nullable=True),
    sa.Column('source_port', sa.Integer(), nullable=True),
    sa.Column('dest_ip', sa.String(), nullable=True),
    sa.Column('dest_port', sa.Integer(), nullable=True),
    sa.Column('network_protocol', sa.String(), nullable=True),
    sa.Column('user_name', sa.String(), nullable=True),
    sa.Column('device_vendor', sa.String(), nullable=True),
    sa.Column('device_product', sa.String(), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('parser_id', sa.String(), nullable=True),
    sa.Column('parser_version', sa.String(), nullable=True),
    sa.Column('parser_format', sa.String(), nullable=True),
    sa.Column('mapping_method', sa.String(), nullable=True),
    sa.Column('normalization_confidence', sa.Float(), nullable=True),
    sa.Column('risk_score', sa.Integer(), nullable=True),
    sa.Column('risk_level', sa.String(), nullable=True),
    sa.Column('raw_sha256', sa.String(), nullable=True),
    sa.Column('normalized_sha256', sa.String(), nullable=True),
    sa.Column('raw_location', sa.String(), nullable=True),
    sa.Column('quality_score', sa.Integer(), nullable=True),
    sa.Column('integrity_verified', sa.Boolean(), nullable=True),
    sa.Column('redacted_fields', sa.JSON(), nullable=True),
    sa.Column('canonical_json', sa.JSON(), nullable=True),
    sa.Column('severity', sa.String(), nullable=True),
    sa.Column('action', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
    sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index(op.f('ix_normalized_events_event_id'), 'normalized_events', ['event_id'], unique=False)
    op.create_index(op.f('ix_normalized_events_timestamp'), 'normalized_events', ['timestamp'], unique=False)
    op.create_index(op.f('ix_normalized_events_source_id'), 'normalized_events', ['source_id'], unique=False)
    op.create_index(op.f('ix_normalized_events_source_ip'), 'normalized_events', ['source_ip'], unique=False)
    op.create_index(op.f('ix_normalized_events_risk_level'), 'normalized_events', ['risk_level'], unique=False)
    op.create_index(op.f('ix_normalized_events_severity'), 'normalized_events', ['severity'], unique=False)
    op.create_index(op.f('ix_normalized_events_action'), 'normalized_events', ['action'], unique=False)
    op.create_index('ix_normalized_events_ts_src', 'normalized_events', ['timestamp', 'source_id'], unique=False)

    # dlq_events
    op.create_table('dlq_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('source_id', sa.String(), nullable=True),
    sa.Column('raw_log', sa.Text(), nullable=True),
    sa.Column('raw_location', sa.String(), nullable=True),
    sa.Column('failure_reason', sa.String(), nullable=False),
    sa.Column('failure_detail', sa.Text(), nullable=True),
    sa.Column('parser_id', sa.String(), nullable=True),
    sa.Column('parser_version', sa.String(), nullable=True),
    sa.Column('retry_count', sa.Integer(), nullable=True),
    sa.Column('max_retries', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('assigned_to', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dlq_events_id'), 'dlq_events', ['id'], unique=False)
    op.create_index(op.f('ix_dlq_events_event_id'), 'dlq_events', ['event_id'], unique=False)
    op.create_index(op.f('ix_dlq_events_status'), 'dlq_events', ['status'], unique=False)
    op.create_index(op.f('ix_dlq_events_created_at'), 'dlq_events', ['created_at'], unique=False)

    # replay_jobs
    op.create_table('replay_jobs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('source_id', sa.String(), nullable=True),
    sa.Column('time_range_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('time_range_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('old_parser_version', sa.String(), nullable=True),
    sa.Column('new_parser_version', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('progress', sa.Integer(), nullable=True),
    sa.Column('total_events', sa.Integer(), nullable=True),
    sa.Column('processed_events', sa.Integer(), nullable=True),
    sa.Column('changed_events', sa.Integer(), nullable=True),
    sa.Column('requested_by', sa.String(), nullable=True),
    sa.Column('approved_by', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_replay_jobs_id'), 'replay_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_replay_jobs_status'), 'replay_jobs', ['status'], unique=False)

    # parsers
    op.create_table('parsers',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('vendor', sa.String(), nullable=True),
    sa.Column('device_type', sa.String(), nullable=True),
    sa.Column('format_type', sa.String(), nullable=False),
    sa.Column('version', sa.String(), nullable=False),
    sa.Column('config_yaml', sa.Text(), nullable=True),
    sa.Column('config_json', sa.JSON(), nullable=True),
    sa.Column('sample_log', sa.Text(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_by', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_parsers_id'), 'parsers', ['id'], unique=False)
    op.create_index(op.f('ix_parsers_vendor'), 'parsers', ['vendor'], unique=False)
    op.create_index(op.f('ix_parsers_status'), 'parsers', ['status'], unique=False)

    # parser_versions
    op.create_table('parser_versions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('parser_id', sa.String(), nullable=False),
    sa.Column('version', sa.String(), nullable=False),
    sa.Column('config_yaml', sa.Text(), nullable=True),
    sa.Column('config_json', sa.JSON(), nullable=True),
    sa.Column('changelog', sa.Text(), nullable=True),
    sa.Column('published_by', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['parser_id'], ['parsers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_parser_versions_id'), 'parser_versions', ['id'], unique=False)
    op.create_index(op.f('ix_parser_versions_parser_id'), 'parser_versions', ['parser_id'], unique=False)

    # correlation_rules
    op.create_table('correlation_rules',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('severity', sa.String(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=True),
    sa.Column('condition', sa.JSON(), nullable=True),
    sa.Column('threshold', sa.Integer(), nullable=True),
    sa.Column('time_window_seconds', sa.Integer(), nullable=True),
    sa.Column('matches_24h', sa.Integer(), nullable=True),
    sa.Column('last_matched_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_correlation_rules_id'), 'correlation_rules', ['id'], unique=False)

    # users
    op.create_table('users',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('role_name', sa.String(), nullable=True),
    sa.Column('organization_id', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('last_active', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # roles
    op.create_table('roles',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('permissions', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_roles_id'), 'roles', ['id'], unique=False)

    # organizations
    op.create_table('organizations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=True),
    sa.Column('sector', sa.String(), nullable=True),
    sa.Column('contact_email', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_organizations_id'), 'organizations', ['id'], unique=False)

    # integrations
    op.create_table('integrations',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('config', sa.JSON(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('last_test_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_test_result', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_integrations_id'), 'integrations', ['id'], unique=False)

    # threat_indicators
    op.create_table('threat_indicators',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('value', sa.String(), nullable=False),
    sa.Column('threat_type', sa.String(), nullable=True),
    sa.Column('severity', sa.String(), nullable=False),
    sa.Column('source', sa.String(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.Column('hits', sa.Integer(), nullable=True),
    sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_threat_indicators_id'), 'threat_indicators', ['id'], unique=False)
    op.create_index(op.f('ix_threat_indicators_type'), 'threat_indicators', ['type'], unique=False)
    op.create_index(op.f('ix_threat_indicators_value'), 'threat_indicators', ['value'], unique=False)

    # privacy_policies
    op.create_table('privacy_policies',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('rules', sa.JSON(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=True),
    sa.Column('scope', sa.String(), nullable=True),
    sa.Column('created_by', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_privacy_policies_id'), 'privacy_policies', ['id'], unique=False)
    
    # Update existing tables
    op.add_column('sources', sa.Column('organization_id', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('ip_address', sa.String(), nullable=True))
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)


def downgrade() -> None:
    pass
