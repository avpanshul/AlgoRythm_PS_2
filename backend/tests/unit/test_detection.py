"""Tests for silent-source/volume-spike/peer-deviation detection
(app/analytics/detection.py). This module had no test coverage at all before
scripts/demo_flow.py's live run against a real, non-empty SQLite DB
surfaced a real crash: `detect_silent_sources` compared a timezone-aware
`datetime.now(timezone.utc)` against a value read back from SQLite, which
silently drops tzinfo on round-trip -- `TypeError: can't compare
offset-naive and offset-aware datetimes`. Every test here uses a real,
non-empty SQLite DB (not an empty one, which would never have exercised the
comparison that crashed).
"""
import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.all import Source, NormalizedEvent
from app.analytics.detection import detect_silent_sources, detect_volume_anomalies, detect_peer_deviation


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _mk_event(db, source_id, ts):
    db.add(NormalizedEvent(
        event_id=f"evt-{uuid.uuid4().hex[:12]}", timestamp=ts, source_id=source_id,
        event_data={"category": "test"},
    ))


class TestSilentSourceDetection:
    def test_does_not_crash_against_a_real_non_empty_sqlite_db(self):
        """The exact regression: this must not raise TypeError comparing
        offset-naive (SQLite round-trip) vs offset-aware (datetime.now())
        datetimes."""
        db = _fresh_db()
        db.add(Source(id="SRC-1", name="SRC-1", enabled=True))
        _mk_event(db, "SRC-1", datetime.now(timezone.utc) - timedelta(hours=2))
        db.commit()

        result = detect_silent_sources(db, silence_minutes=60)  # must not raise
        assert isinstance(result, list)

    def test_flags_a_genuinely_silent_source(self):
        db = _fresh_db()
        db.add(Source(id="SRC-1", name="SRC-1", enabled=True))
        _mk_event(db, "SRC-1", datetime.now(timezone.utc) - timedelta(hours=5))
        db.commit()

        result = detect_silent_sources(db, silence_minutes=60)
        assert len(result) == 1
        assert result[0]["source_id"] == "SRC-1"

    def test_does_not_flag_a_recently_active_source(self):
        db = _fresh_db()
        db.add(Source(id="SRC-1", name="SRC-1", enabled=True))
        _mk_event(db, "SRC-1", datetime.now(timezone.utc) - timedelta(minutes=5))
        db.commit()

        result = detect_silent_sources(db, silence_minutes=60)
        assert result == []

    def test_does_not_flag_a_source_with_no_events_at_all(self):
        """A source that's simply never sent anything isn't 'gone silent'."""
        db = _fresh_db()
        db.add(Source(id="SRC-NEVER-SENT", name="SRC-NEVER-SENT", enabled=True))
        db.commit()

        result = detect_silent_sources(db, silence_minutes=60)
        assert result == []


class TestVolumeAnomalyDetection:
    def test_does_not_crash_against_a_real_non_empty_sqlite_db(self):
        db = _fresh_db()
        db.add(Source(id="SRC-1", name="SRC-1", enabled=True))
        now = datetime.now(timezone.utc)
        for i in range(30):
            _mk_event(db, "SRC-1", now - timedelta(minutes=i))
        db.commit()

        result = detect_volume_anomalies(db, window_minutes=5, baseline_windows=3)  # must not raise
        assert isinstance(result, list)


class TestPeerDeviationDetection:
    def test_does_not_crash_against_a_real_non_empty_sqlite_db(self):
        db = _fresh_db()
        now = datetime.now(timezone.utc)
        for i in range(3):
            sid = f"SRC-{i}"
            db.add(Source(id=sid, name=sid, enabled=True, device_type="firewall"))
            for _ in range(5):
                _mk_event(db, sid, now - timedelta(minutes=1))
        db.commit()

        result = detect_peer_deviation(db, window_minutes=60)  # must not raise
        assert isinstance(result, list)
