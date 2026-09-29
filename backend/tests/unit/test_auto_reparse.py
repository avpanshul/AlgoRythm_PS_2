"""Tests for Item 3: backlog re-parse (app/services/auto_reparse.py).

Real process_raw_event calls against real (test) raw-log files -- per this
project's own no-mocking rule, not a stubbed pipeline. Uses a real
KeyValue-detectable line so reprocessing genuinely succeeds, same as it
would against real DLQ backlog data.
"""
import sys
import os
import hashlib
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.config import settings
from app.core.local_storage import save_raw_log
from app.models.all import DLQEvent, RawEventMetadata, AuditLog
from app.services.auto_reparse import cluster_id_for_parser, reparse_cluster_backlog


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _mk_dlq_backlog_entry(db, cluster_id, raw_log, status="failed"):
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    raw_sha256 = hashlib.sha256(raw_log.encode("utf-8")).hexdigest()
    raw_location = f"test/{event_id}.txt"
    save_raw_log(raw_location, raw_log)
    db.add(RawEventMetadata(
        event_id=event_id, source_id="TEST-SRC", ingestion_protocol="test",
        raw_sha256=raw_sha256, raw_location=raw_location, processing_status="failed",
    ))
    db.add(DLQEvent(
        event_id=event_id, source_id="TEST-SRC", raw_log=raw_log, raw_location=raw_location,
        failure_reason="UnknownFormatError", drain_cluster_id=cluster_id, status=status,
        created_at=datetime.now(timezone.utc),
    ))
    return event_id


class TestClusterIdForParser:
    def test_ai_draft_pack_id_extracts_real_cluster_id(self):
        assert cluster_id_for_parser("ai-draft-42") == "42"

    def test_hand_authored_pack_has_no_cluster(self):
        assert cluster_id_for_parser("syslog_paloalto") is None

    def test_none_input(self):
        assert cluster_id_for_parser(None) is None


class TestReparseClusterBacklog:
    def test_reprocesses_real_recognizable_backlog_events(self):
        db = _fresh_db()
        cluster_id = "test-cluster-1"
        # A real KeyValue line the deterministic parser genuinely recognizes.
        eid1 = _mk_dlq_backlog_entry(db, cluster_id, "src_ip=10.0.0.5 user=alice action=login result=success")
        eid2 = _mk_dlq_backlog_entry(db, cluster_id, "src_ip=10.0.0.6 user=bob action=login result=success")
        db.commit()

        result = reparse_cluster_backlog(db, cluster_id, triggered_by="test-user", batch_size=10)

        assert result["candidates"] == 2
        assert result["resolved"] == 2
        assert result["still_failed"] == 0

        for eid in (eid1, eid2):
            row = db.query(DLQEvent).filter(DLQEvent.event_id == eid).first()
            assert row.status == "resolved"
            assert row.retry_count == 1

    def test_only_touches_the_named_cluster(self):
        db = _fresh_db()
        _mk_dlq_backlog_entry(db, "cluster-A", "src_ip=10.0.0.7 user=carol action=login result=success")
        other_eid = _mk_dlq_backlog_entry(db, "cluster-B", "src_ip=10.0.0.8 user=dan action=login result=success")
        db.commit()

        result = reparse_cluster_backlog(db, "cluster-A", triggered_by="test-user", batch_size=10)

        assert result["candidates"] == 1
        # cluster-B's event untouched
        other = db.query(DLQEvent).filter(DLQEvent.event_id == other_eid).first()
        assert other.status == "failed"
        assert other.retry_count == 0

    def test_capped_by_batch_size(self):
        db = _fresh_db()
        cluster_id = "test-cluster-cap"
        for i in range(5):
            _mk_dlq_backlog_entry(db, cluster_id, f"src_ip=10.0.1.{i} user=u{i} action=login result=success")
        db.commit()

        result = reparse_cluster_backlog(db, cluster_id, triggered_by="test-user", batch_size=2)

        assert result["candidates"] == 2  # capped, not all 5
        assert db.query(DLQEvent).filter(DLQEvent.drain_cluster_id == cluster_id, DLQEvent.status == "failed").count() == 3

    def test_idempotent_second_run_skips_already_resolved(self):
        db = _fresh_db()
        cluster_id = "test-cluster-idem"
        _mk_dlq_backlog_entry(db, cluster_id, "src_ip=10.0.2.1 user=eve action=login result=success")
        db.commit()

        first = reparse_cluster_backlog(db, cluster_id, triggered_by="test-user", batch_size=10)
        second = reparse_cluster_backlog(db, cluster_id, triggered_by="test-user", batch_size=10)

        assert first["resolved"] == 1
        assert second["candidates"] == 0  # nothing left with status="failed"

    def test_writes_a_real_audit_log_entry(self):
        db = _fresh_db()
        cluster_id = "test-cluster-audit"
        _mk_dlq_backlog_entry(db, cluster_id, "src_ip=10.0.3.1 user=frank action=login result=success")
        db.commit()

        reparse_cluster_backlog(db, cluster_id, triggered_by="test-user", batch_size=10)

        audit = db.query(AuditLog).filter(AuditLog.action == "cluster_backlog_reparsed", AuditLog.entity_id == cluster_id).first()
        assert audit is not None
        assert audit.user == "test-user"
        assert audit.after_state["resolved"] == 1
