"""Tests for retention and legal hold (ULPF-master-prompt.md D10).

Directly targets the spec's own acceptance criterion: "expired event
deleted + proof logged; held event survives + attempted delete blocked and
logged." Uses a real local_storage-backed raw file (not mocked) so file
deletion is genuinely exercised, not assumed.
"""
import sys
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.all import Source, NormalizedEvent, RawEventMetadata, RetentionPolicy, LegalHold, AuditLog
from app.core.retention import run_retention_sweep, place_hold, release_hold, delete_event


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _mk_event_with_raw_file(db, source_id, age_days, tmp_data_dir):
    """Creates a real event + a real raw file on disk under a temp
    local_storage DATA_DIR, so deletion is tested against a genuine file,
    not a mock."""
    import app.core.local_storage as local_storage
    local_storage.DATA_DIR = tmp_data_dir

    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    raw_location = f"{event_id}.txt"
    local_storage.save_raw_log(raw_location, "real test log content")

    now = datetime.now(timezone.utc) - timedelta(days=age_days)
    db.add(NormalizedEvent(
        event_id=event_id, timestamp=now, source_id=source_id,
        raw_sha256="deadbeef", event_data={"category": "test"},
    ))
    db.add(RawEventMetadata(
        event_id=event_id, source_id=source_id, ingestion_protocol="test",
        raw_sha256="deadbeef", raw_location=raw_location,
    ))
    db.commit()
    return event_id, os.path.join(tmp_data_dir, raw_location)


def _mk_source(db, source_id="SRC-1"):
    db.add(Source(id=source_id, name=source_id))
    db.commit()


class TestRetentionSweep:
    def test_expired_event_is_deleted_and_the_deletion_is_audit_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _fresh_db()
            _mk_source(db)
            db.add(RetentionPolicy(source_id="SRC-1", retention_days=30, enabled=True))
            db.commit()

            event_id, file_path = _mk_event_with_raw_file(db, "SRC-1", age_days=45, tmp_data_dir=tmp)
            assert os.path.exists(file_path)

            result = run_retention_sweep(db)

            assert result["SRC-1"]["deleted"] == 1
            assert db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).first() is None
            assert db.query(RawEventMetadata).filter(RawEventMetadata.event_id == event_id).first() is None
            assert not os.path.exists(file_path)  # the real file is genuinely gone

            audit = db.query(AuditLog).filter(AuditLog.action == "event_deleted", AuditLog.entity_id == event_id).first()
            assert audit is not None
            assert audit.after_state["raw_file_deleted"] is True

    def test_event_within_retention_window_survives(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _fresh_db()
            _mk_source(db)
            db.add(RetentionPolicy(source_id="SRC-1", retention_days=30, enabled=True))
            db.commit()

            event_id, file_path = _mk_event_with_raw_file(db, "SRC-1", age_days=5, tmp_data_dir=tmp)

            run_retention_sweep(db)

            assert db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).first() is not None
            assert os.path.exists(file_path)

    def test_disabled_policy_deletes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _fresh_db()
            _mk_source(db)
            db.add(RetentionPolicy(source_id="SRC-1", retention_days=30, enabled=False))
            db.commit()
            event_id, _ = _mk_event_with_raw_file(db, "SRC-1", age_days=90, tmp_data_dir=tmp)

            run_retention_sweep(db)

            assert db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).first() is not None


class TestLegalHold:
    def test_held_source_survives_an_otherwise_expired_sweep(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _fresh_db()
            _mk_source(db)
            db.add(RetentionPolicy(source_id="SRC-1", retention_days=30, enabled=True))
            db.commit()
            event_id, file_path = _mk_event_with_raw_file(db, "SRC-1", age_days=90, tmp_data_dir=tmp)

            place_hold(db, "SRC-1", reason="litigation hold -- case #123", created_by="legal-team")
            result = run_retention_sweep(db)

            assert result["SRC-1"]["skipped"] is True
            assert db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).first() is not None
            assert os.path.exists(file_path)

    def test_manual_delete_of_held_event_is_blocked_and_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _fresh_db()
            _mk_source(db)
            event_id, file_path = _mk_event_with_raw_file(db, "SRC-1", age_days=90, tmp_data_dir=tmp)
            hold = place_hold(db, "SRC-1", reason="litigation hold", created_by="legal-team")

            result = delete_event(db, event_id, deleted_by="rogue-admin")

            assert result["status"] == "blocked"
            assert hold.id in result["hold_id"]
            # Real proof it survived, not just a status string:
            assert db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).first() is not None
            assert os.path.exists(file_path)

            audit = db.query(AuditLog).filter(AuditLog.action == "event_delete_blocked_by_legal_hold").first()
            assert audit is not None
            assert audit.user == "rogue-admin"
            assert "legal hold" in audit.reason

    def test_after_hold_released_deletion_proceeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _fresh_db()
            _mk_source(db)
            event_id, file_path = _mk_event_with_raw_file(db, "SRC-1", age_days=90, tmp_data_dir=tmp)
            hold = place_hold(db, "SRC-1", reason="litigation hold", created_by="legal-team")

            blocked = delete_event(db, event_id, deleted_by="admin")
            assert blocked["status"] == "blocked"

            release_hold(db, hold.id, released_by="legal-team")
            allowed = delete_event(db, event_id, deleted_by="admin")

            assert allowed["status"] == "deleted"
            assert not os.path.exists(file_path)

    def test_manual_delete_of_non_held_event_succeeds_and_is_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = _fresh_db()
            _mk_source(db)
            event_id, file_path = _mk_event_with_raw_file(db, "SRC-1", age_days=1, tmp_data_dir=tmp)

            result = delete_event(db, event_id, deleted_by="admin")

            assert result["status"] == "deleted"
            assert not os.path.exists(file_path)
            audit = db.query(AuditLog).filter(AuditLog.action == "event_deleted", AuditLog.entity_id == event_id).first()
            assert audit is not None
