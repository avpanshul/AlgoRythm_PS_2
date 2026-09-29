"""Tests for source contract fingerprinting / drift detection
(ULPF-master-prompt.md C2: "a changed structure marks the source
'Format changed' and requires review before its events are exported")."""
import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.all import NormalizedEvent, SourceFingerprint, AuditLog
from app.analytics import drift as drift_module
from app.analytics.drift import check_source_drift, approve_new_fingerprint


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _mk_event(db, source_id, canonical_unmapped=None, source_ip="10.0.0.1"):
    from datetime import datetime, timezone
    eid = f"evt-{uuid.uuid4().hex[:12]}"
    db.add(NormalizedEvent(
        event_id=eid, timestamp=datetime.now(timezone.utc), source_id=source_id,
        source_ip=source_ip, event_data={"category": "test"},
        canonical_json={"unmapped": canonical_unmapped or {}},
    ))
    return eid


class TestFirstObservation:
    def test_first_check_creates_a_baseline_not_a_drift_flag(self):
        db = _fresh_db()
        for _ in range(10):
            _mk_event(db, "SRC-1", canonical_unmapped={"vendor_field_a": "x", "vendor_field_b": "y"})
        db.commit()

        result = check_source_drift(db, "SRC-1")
        assert result["SRC-1"]["status"] == "baseline_created"

        fp = db.query(SourceFingerprint).filter(SourceFingerprint.source_id == "SRC-1").first()
        assert fp.drift_detected is False
        assert "source_ip" in fp.field_names
        assert "unmapped.vendor_field_a" in fp.field_names


class TestDriftDetection:
    def test_stable_shape_across_two_checks_is_not_flagged(self):
        db = _fresh_db()
        for _ in range(10):
            _mk_event(db, "SRC-1", canonical_unmapped={"vendor_field_a": "x"})
        db.commit()
        check_source_drift(db, "SRC-1")

        for _ in range(10):
            _mk_event(db, "SRC-1", canonical_unmapped={"vendor_field_a": "z"})
        db.commit()
        result = check_source_drift(db, "SRC-1")

        assert result["SRC-1"]["status"] == "stable"

    def test_a_real_shape_change_is_flagged_as_drift(self, monkeypatch):
        """Simulates a vendor renaming a field -- the exact real-world event
        this feature exists to catch. Uses a small SAMPLE_SIZE so the
        "recent window" genuinely excludes the old-format events once
        enough new-format ones arrive, matching how a real, higher-volume
        source behaves without needing to generate 50+ events per test."""
        monkeypatch.setattr(drift_module, "SAMPLE_SIZE", 10)
        db = _fresh_db()
        for _ in range(10):
            _mk_event(db, "SRC-1", canonical_unmapped={"old_field_name": "x", "another_field": "y"})
        db.commit()
        check_source_drift(db, "SRC-1")

        # Vendor "renames" old_field_name -> new_field_name in a firmware update.
        for _ in range(10):
            _mk_event(db, "SRC-1", canonical_unmapped={"new_field_name": "x", "another_field": "y"})
        db.commit()
        result = check_source_drift(db, "SRC-1")

        assert result["SRC-1"]["status"] == "drift_detected"
        assert "unmapped.new_field_name" in result["SRC-1"]["added"]
        assert "unmapped.old_field_name" in result["SRC-1"]["removed"]

        fp = db.query(SourceFingerprint).filter(SourceFingerprint.source_id == "SRC-1").first()
        assert fp.drift_detected is True
        # The baseline is NOT silently updated -- still the old shape.
        assert "unmapped.old_field_name" in fp.field_names

        audit = db.query(AuditLog).filter(AuditLog.action == "source_drift_detected").first()
        assert audit is not None

    def test_a_single_field_rename_among_many_stable_fields_is_still_caught(self, monkeypatch):
        """Real finding from scripts/demo_flow.py's live run: with ~9 total
        fields, renaming just one still leaves 0.8 Jaccard similarity, which
        a naive threshold (this feature's first version used 0.7) would
        treat as "stable" -- missing exactly the realistic case (a vendor
        renames one field in a firmware update) this feature exists for."""
        monkeypatch.setattr(drift_module, "SAMPLE_SIZE", 10)
        db = _fresh_db()
        many_fields_old = {"a": "1", "b": "2", "c": "3", "d": "4", "e": "5", "f": "6", "g": "7", "h": "8"}
        for _ in range(10):
            _mk_event(db, "SRC-1", canonical_unmapped=many_fields_old)
        db.commit()
        check_source_drift(db, "SRC-1")

        many_fields_renamed = dict(many_fields_old)
        del many_fields_renamed["a"]
        many_fields_renamed["a_renamed"] = "1"
        for _ in range(10):
            _mk_event(db, "SRC-1", canonical_unmapped=many_fields_renamed)
        db.commit()
        result = check_source_drift(db, "SRC-1")

        assert result["SRC-1"]["status"] == "drift_detected"

    def test_drifted_source_requires_explicit_approval_to_rebaseline(self, monkeypatch):
        monkeypatch.setattr(drift_module, "SAMPLE_SIZE", 10)
        db = _fresh_db()
        for _ in range(10):
            _mk_event(db, "SRC-1", canonical_unmapped={"old_field": "x"})
        db.commit()
        check_source_drift(db, "SRC-1")
        for _ in range(10):
            _mk_event(db, "SRC-1", canonical_unmapped={"new_field": "x"})
        db.commit()
        check_source_drift(db, "SRC-1")

        fp_before = db.query(SourceFingerprint).filter(SourceFingerprint.source_id == "SRC-1").first()
        assert fp_before.drift_detected is True

        approved = approve_new_fingerprint(db, "SRC-1", approved_by="parser-author-1")

        assert approved.drift_detected is False
        assert "unmapped.new_field" in approved.field_names
        assert "unmapped.old_field" not in approved.field_names

        audit = db.query(AuditLog).filter(AuditLog.action == "source_drift_approved").first()
        assert audit is not None
        assert audit.user == "parser-author-1"
