from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, JSON, ForeignKey, Text, Index
from sqlalchemy.sql import func
from app.core.database import Base
from app.core import db_encryption


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
    

class PlatformSetting(Base):
    """Real, persisted key-value platform preferences (Settings page: General
    tab's Platform Name/Default Timezone, Security tab's session timeout).
    Deliberately a plain key-value table, not one column per setting -- this
    only backs settings that a real feature actually reads (see
    app/api/v1/settings.py's SETTING_KEYS), not a speculative catch-all."""
    __tablename__ = "platform_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(String, nullable=True)


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
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    # Hash chain (ULPF-master-prompt.md Part D5: tamper-evident admin audit
    # log): populated by the before_insert listener in this module, not by
    # callers -- every AuditLog(...) construction site gets this for free,
    # and none can accidentally skip it. See verify_audit_chain() below.
    prev_hash = Column(String, nullable=True)
    hash = Column(String, nullable=True)


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

    # Set by app/analytics/correlation.py when this event matches a
    # cross-source/cross-event correlation rule (ULPF-phase2-prompt.md E1).
    # Null for the large majority of events that don't match any rule.
    correlation_id = Column(String, nullable=True, index=True)

    # Set by app/ai/sentinel.py once this event has been folded into its
    # source_ip's behavioral profile (ULPF-phase2-prompt.md E7a). Makes
    # update_all_profiles() safe to re-run without double-counting the same
    # event into risk_score/reason_log, the same idempotency property
    # app/analytics/correlation.py's dedupe-by-event-id-set already has.
    sentinel_processed_at = Column(DateTime(timezone=True), nullable=True)

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
    drain_cluster_id = Column(String, nullable=True, index=True)  # Drain3 cluster this unknown-format event was grouped into
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ─── Integrity: Merkle log + signed checkpoints ────────────────────

class MerkleLeaf(Base):
    """Append-only log of leaf hashes, one per normalized event, in ingestion order.
    `sequence` is the leaf index used for inclusion proofs."""
    __tablename__ = "merkle_leaves"

    sequence = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, nullable=False, unique=True, index=True)
    leaf_hash = Column(String, nullable=False)  # hex SHA-256, RFC 6962 leaf-hashed
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Checkpoint(Base):
    """A signed snapshot of the Merkle tree at a given size. Anyone holding the
    public key can verify `signature` over `f"{tree_size}:{root_hash}"` without
    trusting this system -- see app/integrity/signing.py."""
    __tablename__ = "checkpoints"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tree_size = Column(Integer, nullable=False)
    root_hash = Column(String, nullable=False)   # hex SHA-256 Merkle root
    signature = Column(String, nullable=False)   # hex signature (see `algorithm`)
    public_key = Column(String, nullable=False)  # hex public key used to sign
    # "ed25519" (demo-grade file-backed key) or "ecdsa-p256-hsm" (PKCS#11 --
    # see app/integrity/signing.py, Part D3). Nullable-in-practice rows from
    # before this column existed are treated as "ed25519" by every reader.
    algorithm = Column(String, nullable=True, default="ed25519")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Scheduled self-verification (checkpoint_scheduler.py re-walks old
    # checkpoints rather than only ever issuing new ones). None = never
    # re-verified since issuance.
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    last_verification_status = Column(String, nullable=True)  # valid | tamper_detected
    last_verification_detail = Column(Text, nullable=True)

    # Multi-party witnessing (app/integrity/witness.py) -- a second,
    # independent signature over the same f"{tree_size}:{root_hash}" message.
    witness_signature = Column(String, nullable=True)
    witness_public_key = Column(String, nullable=True)
    witness_algorithm = Column(String, nullable=True)
    witness_source = Column(String, nullable=True)  # local | external
    witnessed_at = Column(DateTime(timezone=True), nullable=True)

    # RFC 3161 trusted timestamp (app/integrity/rfc3161.py).
    rfc3161_status = Column(String, nullable=True, default="not_configured")  # not_configured | obtained | failed
    rfc3161_token_b64 = Column(Text, nullable=True)
    rfc3161_tsa_url = Column(String, nullable=True)


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
    # verified: matched against real production traffic from that vendor.
    # fixture: passes its own fixture test (sample_log) but not seen on real
    # traffic. experimental: exists but hasn't passed its fixture test yet.
    # Defaults to fixture, never verified, unless explicitly set -- a pack is
    # never allowed to claim "verified" just by being registered.
    coverage_status = Column(String, nullable=False, default="fixture", index=True)
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

class Case(Base):
    """Incident response case (ULPF-phase2-prompt.md E6). Deliberately a
    separate table from CorrelatedIncident (E1) rather than overloading that
    one: a CorrelatedIncident is a specific rule match with a fixed schema
    (rule_id, event_ids, stage_summary, ...); a Case is the general-purpose
    thing an analyst opens, works, and closes -- it can reference a
    correlation match that triggered it (`correlation_id`) or stand alone
    for a manually-opened case, and carries a severity tier that drives
    notification behavior (see app/notifications/)."""
    __tablename__ = "cases"

    id = Column(String, primary_key=True, index=True)  # "case-" + uuid4 hex
    correlation_id = Column(String, ForeignKey("correlated_incidents.id"), nullable=True, index=True)
    title = Column(String, nullable=False)
    severity = Column(String, nullable=False, default="medium", index=True)  # low/medium/high/critical
    status = Column(String, nullable=False, default="open", index=True)  # open/investigating/resolved/false_positive
    owner = Column(String, nullable=True)
    notes = Column(JSON, nullable=True)  # list[{timestamp, user, note}]
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class RetentionPolicy(Base):
    """Per-source retention (ULPF-master-prompt.md D10). One row per source_id
    -- app/core/retention.py's sweep deletes NormalizedEvent/raw-vault content
    older than `retention_days` for that source, unless an active LegalHold
    covers it. Deleting content never deletes the corresponding MerkleLeaf
    (just a hash, no content) -- the tree and every checkpoint over it stay
    valid and provable even after the event's own content is gone, which is
    the actual point of separating "prove this existed" from "retain the
    content forever" (see docs/threat-model.md)."""
    __tablename__ = "retention_policies"

    source_id = Column(String, ForeignKey("sources.id"), primary_key=True)
    retention_days = Column(Integer, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SourceFingerprint(Base):
    """A source's accepted field-name schema (ULPF-master-prompt.md C2:
    "source contract fingerprint... a changed structure marks the source
    'Format changed' and requires review before its events are exported").
    One row per source_id; `field_names` is the sorted list of canonical +
    unmapped field names actually populated across a recent sample of that
    source's real events -- a real vendor changing their log format shows up
    as this set changing, without needing to hand-write a schema per
    vendor."""
    __tablename__ = "source_fingerprints"

    source_id = Column(String, ForeignKey("sources.id"), primary_key=True)
    field_names = Column(JSON, nullable=False)  # sorted list[str] -- the accepted baseline
    sample_count = Column(Integer, nullable=False)
    drift_detected = Column(Boolean, nullable=False, default=False, index=True)
    drift_detail = Column(JSON, nullable=True)  # {"added": [...], "removed": [...], "similarity": 0.x}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SavedQuery(Base):
    """A named, reusable event-search filter (ULPF-phase2-prompt.md E3
    threat-hunting workspace). `filter` mirrors GET /events' own query
    params so a saved query is directly replayable against that same
    endpoint, not a second, parallel filter language."""
    __tablename__ = "saved_queries"

    id = Column(String, primary_key=True, index=True)  # "query-" + uuid4 hex
    name = Column(String, nullable=False)
    filter = Column(JSON, nullable=False)  # {"q": ..., "severity": ..., "risk_level": ..., "source_id": ...}
    owner = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LegalHold(Base):
    """Blocks retention deletion for a source while active (`released_at` is
    null). Scoped to source_id, matching the master prompt's own
    LegalHold{source_id, reason} shape -- a hold protects everything from
    that source, not individual events."""
    __tablename__ = "legal_holds"

    id = Column(String, primary_key=True, index=True)  # "hold-" + uuid4 hex
    source_id = Column(String, ForeignKey("sources.id"), nullable=False, index=True)
    reason = Column(String, nullable=False)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    released_at = Column(DateTime(timezone=True), nullable=True)
    released_by = Column(String, nullable=True)


class OnCallContact(Base):
    """On-call registry (E6). Empty by default -- a real admin adds real
    contacts through the API; nothing here is seeded, per this project's
    standing no-fabricated-data rule (a fake on-call contact is exactly the
    kind of thing that rule exists to prevent)."""
    __tablename__ = "oncall_contacts"

    id = Column(String, primary_key=True, index=True)  # "contact-" + uuid4 hex
    name = Column(String, nullable=False)
    channel = Column(String, nullable=False)  # "sms" (the channel this deployment chose) or "console" (dev/demo)
    address = Column(String, nullable=False)  # phone number for sms, arbitrary label for console
    escalation_order = Column(Integer, nullable=False, default=0, index=True)  # lower = notified first
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    """One notification attempt for a Case, to one contact (E6). `dedup_key`
    and the rate-limit check in app/notifications/engine.py are what stop a
    still-open case from re-notifying the same contact every time something
    re-touches it; `sent_at`/`acknowledged_at` are the raw data behind the
    time-to-acknowledge metric E6 exists to produce."""
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, index=True)  # "notif-" + uuid4 hex
    case_id = Column(String, ForeignKey("cases.id"), nullable=False, index=True)
    contact_id = Column(String, ForeignKey("oncall_contacts.id"), nullable=True)
    channel = Column(String, nullable=False)
    dedup_key = Column(String, nullable=False, index=True)  # f"{case_id}:{severity}" -- see engine.py
    status = Column(String, nullable=False, default="sent")  # sent/failed/not_configured/rate_limited/deduped/acknowledged/escalated
    detail = Column(String, nullable=True)  # error/skip reason, or the gateway's own response, if any
    sent_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String, nullable=True)
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EntityProfile(Base):
    """Persistent per-entity behavioral profile ("Sentinel",
    ULPF-phase2-prompt.md E7a) -- built and updated by app/ai/sentinel.py
    from real event history only, never from a synthetic/labeled dataset.
    `risk_score` accumulates across many small anomalies over time rather
    than resetting per event; `reason_log` is what makes that number
    explainable rather than a bare accumulator."""
    __tablename__ = "entity_profiles"

    entity_id = Column(String, primary_key=True, index=True)  # currently always an IP
    entity_type = Column(String, nullable=False, default="ip")
    known_dest_ports = Column(JSON, nullable=True)  # list[int]
    known_protocols = Column(JSON, nullable=True)  # list[str]
    known_peers = Column(JSON, nullable=True)  # list[str] (dest_ip values seen)
    risk_score = Column(Float, nullable=False, default=0.0, index=True)
    reason_log = Column(JSON, nullable=True)  # list[{timestamp, event_id, reason, description, contribution, score_after}]
    event_count = Column(Integer, nullable=False, default=0)
    last_event_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CorrelatedIncident(Base):
    """A cross-source/cross-event correlation match (ULPF-phase2-prompt.md
    E1). `id` doubles as the `correlation_id` stamped onto every matched
    NormalizedEvent row -- the UI can pull the whole chain by that ID. Also
    the seed object for E6 case management later (status/owner fields are
    already here so that phase can build on this table rather than a second
    parallel one)."""
    __tablename__ = "correlated_incidents"

    id = Column(String, primary_key=True, index=True)  # uuid; == correlation_id
    rule_id = Column(String, nullable=False, index=True)
    rule_name = Column(String, nullable=False)
    correlate_key = Column(String, nullable=False, index=True)  # e.g. the shared source_ip
    event_ids = Column(JSON, nullable=False)  # list[str] of NormalizedEvent.event_id
    distinct_source_count = Column(Integer, nullable=False)
    stage_summary = Column(JSON, nullable=True)  # {stage_name: matched_event_count}
    first_event_at = Column(DateTime(timezone=True), nullable=False)
    last_event_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False, default="open", index=True)  # open/investigating/resolved/false_positive
    owner = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AgentReasoningTraceEntry(Base):
    """Item 5: one real attempt of the agent refine loop
    (app/services/pack_drafting.py) -- every attempt is stored, not just the
    final one, so "the agent tried, failed, and tried differently" is a real,
    inspectable record (GET /unknown-clusters/{cluster_id}/reasoning-trace),
    never summarized away or silently overwritten."""
    __tablename__ = "agent_reasoning_trace"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cluster_id = Column(String, nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    feedback_used = Column(Text, nullable=True)  # None for attempt 1 (no prior failure to react to)
    field_classifications = Column(JSON, nullable=False)  # full classify_sample_fields() output for this attempt
    mapped_field_count = Column(Integer, nullable=False)
    unmapped_field_count = Column(Integer, nullable=False)
    fixture_avg_mapped_per_sample = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Spark(Base):
    """Item 2: an explicit, explainable "this is where an incident started"
    marker (app/services/spark_detection.py) -- closes the real gap an audit
    found: `reconstruct_attack_path` existed but nothing in the codebase ever
    decided *which* entity to trace, or why. Exactly two trigger rules,
    both stated in `reason` at creation time, never a black-box heuristic:
    (1) "correlated_incident" -- the earliest event's entity in a newly
    opened CorrelatedIncident; (2) "risk_threshold" -- an EntityProfile
    whose risk_score first crosses SPARK_RISK_THRESHOLD. Advisory only: this
    marks a real starting point and reconstructs the real path from it, it
    never predicts what an attacker will do next (see `path`'s own
    provenance in reconstruct_attack_path's docstring)."""
    __tablename__ = "sparks"

    id = Column(String, primary_key=True)
    entity = Column(String, nullable=False, index=True)
    trigger_type = Column(String, nullable=False)  # correlated_incident | risk_threshold
    reason = Column(Text, nullable=False)
    source_incident_id = Column(String, nullable=True)
    risk_score = Column(Float, nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    path = Column(JSON, nullable=True)  # reconstruct_attack_path()'s real "path" list
    hop_count = Column(Integer, nullable=False, default=0)
    front = Column(String, nullable=True)
    proximity_watchlist = Column(JSON, nullable=True)


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
    # bcrypt hash of the user's password (passlib). Nullable so existing rows created
    # before auth existed don't break; a null hash means the account cannot log in
    # until a password is set (there is no "no password required" login path).
    password_hash = Column(String, nullable=True)
    last_active = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # MFA (TOTP, RFC 6238) -- Part D1. mfa_secret is set on /auth/mfa/setup
    # but mfa_enabled stays False until the user proves possession of it via
    # /auth/mfa/enable (a code that actually verifies), so a setup call that's
    # never completed can't silently gate login. Encrypted at rest via
    # app/core/db_encryption.py (it's a long-lived shared secret, not a hash).
    mfa_secret = Column(db_encryption.EncryptedString(), nullable=True)
    mfa_enabled = Column(Boolean, nullable=False, default=False)

    # Account lockout (Part D1). Reset to 0 on every successful login;
    # incremented on every failed password check. locked_until is checked
    # (and honored) before the password is even compared, so a locked
    # account can't be brute-forced during its lockout window either.
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)


class IngestToken(Base):
    """Ingest-scoped bearer tokens (Part D1: separate ingest-vs-admin token
    identities). Issuing one (POST /admin/ingest-tokens) mints a JWT whose
    `scope` claim is "ingest" rather than "full" -- app/core/deps.py's
    get_current_user rejects an ingest-scoped token on every router except
    the ingestion endpoints, so a token minted for a syslog forwarder can
    physically not call /admin/users or /settings even if it leaks. This
    table exists so a leaked/rotated token can actually be revoked (JWTs are
    otherwise stateless/unrevokable until they expire) -- every ingest token
    carries its row's id as its `jti` claim, checked against `revoked` on
    every request.
    """
    __tablename__ = "ingest_tokens"

    id = Column(String, primary_key=True)  # jti embedded in the JWT
    source_id = Column(String, ForeignKey("sources.id"), nullable=True)
    name = Column(String, nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked = Column(Boolean, nullable=False, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class IngestionRun(Base):
    """One row per automatic-ingestion run (app/services/auto_ingest.py --
    twice-daily real-data re-ingestion). `id` is a deterministic key for
    scheduled runs -- "{YYYY-MM-DD}-{HH:MM}" for the slot it belongs to, e.g.
    "2026-09-28-08:00" -- not a random uuid. That's the actual
    duplicate-run-prevention mechanism: two processes (or one process retried
    after a crash) racing to run the same day's 08:00 slot both try to
    INSERT this exact primary key, and the DB itself rejects the second one
    with an IntegrityError -- no separate lock table or advisory lock
    needed. Manual/CLI-triggered runs use "manual-{uuid4}" instead, since
    they don't belong to a slot that could collide."""
    __tablename__ = "ingestion_runs"

    id = Column(String, primary_key=True)
    trigger = Column(String, nullable=False)  # scheduled | manual | startup_catchup
    status = Column(String, nullable=False, default="running")  # running | completed | failed
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    new_events_ingested = Column(Integer, nullable=False, default=0)
    skipped_duplicates = Column(Integer, nullable=False, default=0)
    dlq_count = Column(Integer, nullable=False, default=0)
    format_breakdown = Column(JSON, nullable=True)
    corpus_exhausted = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)


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


class NormalizedEventVersion(Base):
    """Real fix for a real gap: replay re-normalizing an already-normalized
    event overwrote the NormalizedEvent row in place, with no history kept
    of what it looked like before -- an "append new versions, never
    overwrite" violation of this project's own stated design principle
    (docs/GAP_REPORT.md's replay row). This table archives the pre-replay
    snapshot (the exact same fields replay is about to change) before the
    overwrite happens, so a prior normalization is always recoverable, not
    silently lost. Raw evidence (raw_sha256/raw_location) was never at risk
    either way -- only the *normalized* output changes on replay."""
    __tablename__ = "normalized_event_versions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(String, ForeignKey("normalized_events.event_id"), nullable=False, index=True)
    superseded_by_replay_job_id = Column(Integer, nullable=True)
    event_data = Column(JSON, nullable=True)
    source_ip = Column(String, nullable=True)
    dest_ip = Column(String, nullable=True)
    user_name = Column(String, nullable=True)
    parser_id = Column(String, nullable=True)
    parser_version = Column(String, nullable=True)
    mapping_method = Column(String, nullable=True)
    risk_score = Column(Integer, nullable=True)
    risk_level = Column(String, nullable=True)
    normalized_sha256 = Column(String, nullable=True)
    canonical_json = Column(JSON, nullable=True)
    archived_at = Column(DateTime(timezone=True), server_default=func.now())


# ─── Audit log hash chain (Part D5) ───────────────────────────────
#
# A before_insert listener rather than a helper callers must remember to use:
# every one of the ~7 call sites that do `db.add(AuditLog(...))` gets a
# tamper-evident chain link for free, and no future call site can forget to.
# `hash` covers this row's own fields plus the *previous* row's hash, so
# altering any historical row (fields or timestamp) breaks every hash after
# it -- exactly the property that makes the chain worth walking.

from sqlalchemy import event as _sa_event
from datetime import datetime as _datetime, timezone as _timezone


def _audit_log_hash_payload(entry: "AuditLog", prev_hash: str) -> dict:
    # SQLite (and some DBAPI round-trips generally) silently drops tzinfo on
    # DATETIME columns: a value hashed at insert time as tz-aware UTC comes
    # back naive after a reload/refresh. Normalize to naive-UTC before
    # hashing so the same row hashes identically whether this is called at
    # insert time or during a later verify_audit_chain() walk.
    ts = entry.timestamp
    if ts is not None and ts.tzinfo is not None:
        ts = ts.astimezone(_timezone.utc).replace(tzinfo=None)
    return {
        "prev_hash": prev_hash,
        "user": entry.user,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "before_state": entry.before_state,
        "after_state": entry.after_state,
        "reason": entry.reason,
        "timestamp": ts.isoformat() if ts else None,
    }


@_sa_event.listens_for(AuditLog, "before_insert")
def _chain_audit_log(mapper, connection, target: "AuditLog"):
    from app.integrity.canonical_json import canonicalize
    import hashlib

    if target.timestamp is None:
        target.timestamp = _datetime.now(_timezone.utc)

    prev_row = connection.execute(
        AuditLog.__table__.select().order_by(AuditLog.__table__.c.id.desc()).limit(1)
    ).fetchone()
    prev_hash = prev_row.hash if prev_row and prev_row.hash else ""

    target.prev_hash = prev_hash
    payload = _audit_log_hash_payload(target, prev_hash)
    target.hash = hashlib.sha256(canonicalize(payload).encode("utf-8")).hexdigest()


def verify_audit_chain(db) -> dict:
    """Re-walks the entire audit log in insertion order and recomputes each
    row's hash from its own fields plus the previous row's stored hash,
    exactly as `_chain_audit_log` does at insert time. Returns the first
    broken link found, if any -- a genuinely independent check, not just
    "trust the hash column because it's there"."""
    import hashlib
    from app.integrity.canonical_json import canonicalize

    rows = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    prev_hash = ""
    for row in rows:
        if row.prev_hash != prev_hash:
            return {"valid": False, "broken_at_id": row.id, "reason": "prev_hash does not match preceding row's hash"}
        payload = _audit_log_hash_payload(row, prev_hash)
        expected = hashlib.sha256(canonicalize(payload).encode("utf-8")).hexdigest()
        if row.hash != expected:
            return {"valid": False, "broken_at_id": row.id, "reason": "stored hash does not match recomputed hash -- row was modified after insertion"}
        prev_hash = row.hash
    return {"valid": True, "checked": len(rows)}
