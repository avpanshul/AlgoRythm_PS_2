from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, JSON, ForeignKey, Text, Index
from sqlalchemy.sql import func
from app.core.database import Base


# ─── Existing Models ───────────────────────────────────────────────

class Source(Base):
    __tablename__ = "sources"

    id = Column(String, primary_key=True, index=True) # e.g. FW-001
    name = Column(String, nullable=False)
    vendor = Column(String, nullable=True)
    product = Column(String, nullable=True)
    device_type = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    organization_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MappingRegistry(Base):
    __tablename__ = "mapping_registry"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vendor = Column(String, nullable=False, index=True)
    device_type = Column(String, nullable=True, index=True)
    raw_field = Column(String, nullable=False, index=True)
    canonical_field = Column(String, nullable=False)
    mapping_type = Column(String, nullable=False) # deterministic, template, semantic, llm, manual
    confidence = Column(Float, nullable=False)
    approved = Column(Boolean, default=False)
    approved_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UnknownTemplate(Base):
    __tablename__ = "unknown_templates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cluster_id = Column(String, nullable=False, index=True)
    template_str = Column(String, nullable=False)
    vendor = Column(String, nullable=True)
    event_count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RawEventMetadata(Base):
    __tablename__ = "raw_event_metadata"

    event_id = Column(String, primary_key=True, index=True)
    source_id = Column(String, ForeignKey("sources.id"), nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    ingestion_protocol = Column(String, nullable=False)
    raw_sha256 = Column(String, nullable=False, index=True)
    raw_location = Column(String, nullable=False)
    processing_status = Column(String, nullable=False, default="ingested")
    

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user = Column(String, nullable=False)
    action = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    reason = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)


# ─── New Models: Normalized Events (replaces OpenSearch) ───────────

class NormalizedEvent(Base):
    __tablename__ = "normalized_events"

    event_id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    source_id = Column(String, ForeignKey("sources.id"), nullable=True, index=True)

    # ECS-like fields stored as JSON for flexibility
    event_data = Column(JSON, nullable=True)       # {category, type, action, severity, outcome}
    source_ip = Column(String, nullable=True, index=True)
    source_port = Column(Integer, nullable=True)
    dest_ip = Column(String, nullable=True)
    dest_port = Column(Integer, nullable=True)
    network_protocol = Column(String, nullable=True)
    user_name = Column(String, nullable=True)
    device_vendor = Column(String, nullable=True)
    device_product = Column(String, nullable=True)
    message = Column(Text, nullable=True)

    # Parser info
    parser_id = Column(String, nullable=True)
    parser_version = Column(String, nullable=True)
    parser_format = Column(String, nullable=True)

    # Normalization info
    mapping_method = Column(String, nullable=True)
    normalization_confidence = Column(Float, nullable=True)

    # Risk
    risk_score = Column(Integer, nullable=True)
    risk_level = Column(String, nullable=True, index=True)

    # Provenance
    raw_sha256 = Column(String, nullable=True)
    normalized_sha256 = Column(String, nullable=True)
    raw_location = Column(String, nullable=True)

    # Quality
    quality_score = Column(Integer, nullable=True)
    integrity_verified = Column(Boolean, default=True)

    # Redaction
    redacted_fields = Column(JSON, nullable=True)

    # Full canonical event as JSON (for detail view)
    canonical_json = Column(JSON, nullable=True)

    # Severity as separate indexed column for fast filtering
    severity = Column(String, nullable=True, index=True)
    action = Column(String, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_normalized_events_ts_src', 'timestamp', 'source_id'),
    )


# ─── Dead-Letter Queue ─────────────────────────────────────────────

class DLQEvent(Base):
    __tablename__ = "dlq_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(String, nullable=False, index=True)
    source_id = Column(String, nullable=True)
    raw_log = Column(Text, nullable=True)
    raw_location = Column(String, nullable=True)
    failure_reason = Column(String, nullable=False)
    failure_detail = Column(Text, nullable=True)
    parser_id = Column(String, nullable=True)
    parser_version = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    status = Column(String, nullable=False, default="failed", index=True)  # failed, retrying, resolved, assigned
    assigned_to = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ─── Replay Jobs ───────────────────────────────────────────────────

class ReplayJob(Base):
    __tablename__ = "replay_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=True)
    source_id = Column(String, nullable=True)
    time_range_start = Column(DateTime(timezone=True), nullable=True)
    time_range_end = Column(DateTime(timezone=True), nullable=True)
    old_parser_version = Column(String, nullable=True)
    new_parser_version = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending", index=True)  # pending, running, completed, failed, pending_approval, approved
    progress = Column(Integer, default=0)  # 0-100
    total_events = Column(Integer, default=0)
    processed_events = Column(Integer, default=0)
    changed_events = Column(Integer, default=0)
    requested_by = Column(String, nullable=True)
    approved_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


# ─── Parser Registry ──────────────────────────────────────────────

class Parser(Base):
    __tablename__ = "parsers"

    id = Column(String, primary_key=True, index=True)  # e.g. "syslog_paloalto"
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    vendor = Column(String, nullable=True, index=True)
    device_type = Column(String, nullable=True)
    format_type = Column(String, nullable=False)  # JSON, CEF, Syslog, etc.
    version = Column(String, nullable=False, default="1.0.0")
    config_yaml = Column(Text, nullable=True)  # Full YAML config
    config_json = Column(JSON, nullable=True)   # Parsed config
    sample_log = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="draft", index=True)  # draft, testing, published, deprecated
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ParserVersion(Base):
    __tablename__ = "parser_versions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    parser_id = Column(String, ForeignKey("parsers.id"), nullable=False, index=True)
    version = Column(String, nullable=False)
    config_yaml = Column(Text, nullable=True)
    config_json = Column(JSON, nullable=True)
    changelog = Column(Text, nullable=True)
    published_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─── Correlation Rules ─────────────────────────────────────────────

class CorrelationRule(Base):
    __tablename__ = "correlation_rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String, nullable=False, default="medium")  # low, medium, high, critical
    enabled = Column(Boolean, default=True)
    condition = Column(JSON, nullable=True)  # Rule logic as JSON
    threshold = Column(Integer, nullable=True)
    time_window_seconds = Column(Integer, nullable=True)
    matches_24h = Column(Integer, default=0)
    last_matched_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ─── Users & RBAC ──────────────────────────────────────────────────

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    permissions = Column(JSON, nullable=True)  # List of permission strings
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    role_name = Column(String, nullable=True)
    organization_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")  # active, suspended, inactive
    last_active = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=True)  # Ministry, PSU, CERT, SOC, etc.
    sector = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─── Integrations ──────────────────────────────────────────────────

class Integration(Base):
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # webhook, rest_api, syslog, s3, opensearch
    description = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)  # Connection config (secrets masked)
    enabled = Column(Boolean, default=True)
    status = Column(String, nullable=False, default="configured")  # configured, connected, error, disabled
    last_test_at = Column(DateTime(timezone=True), nullable=True)
    last_test_result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ─── Threat Intelligence ──────────────────────────────────────────

class ThreatIndicator(Base):
    __tablename__ = "threat_indicators"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    type = Column(String, nullable=False, index=True)  # ip, domain, hash, url
    value = Column(String, nullable=False, index=True)
    threat_type = Column(String, nullable=True)  # malware, c2, phishing, brute_force, scanner
    severity = Column(String, nullable=False, default="medium")
    source = Column(String, nullable=True)  # feed name or "manual"
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True)
    hits = Column(Integer, default=0)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─── Privacy Policies ─────────────────────────────────────────────

class PrivacyPolicy(Base):
    __tablename__ = "privacy_policies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    rules = Column(JSON, nullable=True)  # List of {pattern, replacement, field_types}
    enabled = Column(Boolean, default=True)
    scope = Column(String, nullable=True)  # "all", "analytics", "export"
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
