"""Tests for the Sentinel behavioral tracking agent (ULPF-phase2-prompt.md
E7a). Uses hand-constructed NormalizedEvent rows -- test fixtures for
exercising the profiling logic, not a claim about real traffic (same
category as the correlation-engine tests).

Directly targets the master prompt's own acceptance criterion for this
component: "the Sentinel agent's risk score for a test entity visibly rises
across several small, spaced-out synthetic anomalies, with an explainable
reason trail."
"""
import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.all import NormalizedEvent, EntityProfile
from app.ai.sentinel import update_all_profiles, MIN_BASELINE_EVENTS


def _fresh_db(autoflush=True):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=autoflush)()


def _mk_event(db, ts, source_ip, dest_ip="10.0.0.1", dest_port=443, protocol="TCP", severity="info"):
    eid = f"evt-{uuid.uuid4().hex[:12]}"
    db.add(NormalizedEvent(
        event_id=eid, timestamp=ts, source_ip=source_ip,
        dest_ip=dest_ip, dest_port=dest_port, network_protocol=protocol, severity=severity,
        event_data={"category": "network"},
    ))
    return eid


class TestSentinelBaseline:
    def test_repeated_normal_behavior_stays_at_zero_risk(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(20):
            _mk_event(db, now + timedelta(minutes=i), "10.1.1.1", dest_ip="10.0.0.1", dest_port=443, protocol="TCP")
        db.commit()

        update_all_profiles(db)
        profile = db.query(EntityProfile).filter(EntityProfile.entity_id == "10.1.1.1").first()
        assert profile.risk_score == 0
        assert profile.event_count == 20

    def test_score_rises_across_several_spaced_out_anomalies_with_explainable_reasons(self):
        """The master prompt's own E7a acceptance criterion, directly."""
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        # Build a real baseline first (repeated normal behavior).
        for i in range(MIN_BASELINE_EVENTS + 2):
            _mk_event(db, now + timedelta(minutes=i), "10.1.1.2", dest_ip="10.0.0.1", dest_port=443, protocol="TCP")
        db.commit()
        update_all_profiles(db)
        profile = db.query(EntityProfile).filter(EntityProfile.entity_id == "10.1.1.2").first()
        baseline_score = profile.risk_score
        assert baseline_score == 0

        # Anomaly 1, spaced out: a new destination port.
        _mk_event(db, now + timedelta(hours=1), "10.1.1.2", dest_ip="10.0.0.1", dest_port=8080, protocol="TCP")
        db.commit()
        update_all_profiles(db)
        db.refresh(profile)
        score_after_1 = profile.risk_score
        assert score_after_1 > baseline_score

        # Anomaly 2, spaced out further: a new peer.
        _mk_event(db, now + timedelta(hours=2), "10.1.1.2", dest_ip="203.0.113.9", dest_port=443, protocol="TCP")
        db.commit()
        update_all_profiles(db)
        db.refresh(profile)
        score_after_2 = profile.risk_score
        assert score_after_2 > score_after_1

        # Anomaly 3: a new protocol.
        _mk_event(db, now + timedelta(hours=3), "10.1.1.2", dest_ip="10.0.0.1", dest_port=443, protocol="UDP")
        db.commit()
        update_all_profiles(db)
        db.refresh(profile)
        score_after_3 = profile.risk_score
        assert score_after_3 > score_after_2

        # Explainable reason trail: every rise has a reason, and the reasons
        # are attributable to the specific anomalies just introduced.
        reasons = [r["reason"] for r in profile.reason_log]
        assert "new_dest_port" in reasons
        assert "new_peer" in reasons
        assert "new_protocol" in reasons
        for entry in profile.reason_log:
            assert entry["description"]
            assert entry["contribution"] > 0
            assert entry["score_after"] > 0

    def test_cold_start_does_not_flag_the_first_few_events_as_anomalies(self):
        """Without a baseline, everything looks "new" -- the whole point of
        MIN_BASELINE_EVENTS is to not treat an entity's first sighting as
        already anomalous."""
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(MIN_BASELINE_EVENTS - 1):
            _mk_event(db, now + timedelta(minutes=i), "10.1.1.3", dest_ip=f"10.0.0.{i}", dest_port=1000 + i)
        db.commit()

        update_all_profiles(db)
        profile = db.query(EntityProfile).filter(EntityProfile.entity_id == "10.1.1.3").first()
        assert profile.risk_score == 0

    def test_reevaluation_is_idempotent_does_not_double_count(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(MIN_BASELINE_EVENTS + 1):
            _mk_event(db, now + timedelta(minutes=i), "10.1.1.4", dest_ip="10.0.0.1", dest_port=443)
        _mk_event(db, now + timedelta(hours=1), "10.1.1.4", dest_ip="10.0.0.1", dest_port=9999)  # one real anomaly
        db.commit()

        first = update_all_profiles(db)
        profile = db.query(EntityProfile).filter(EntityProfile.entity_id == "10.1.1.4").first()
        score_after_first_run = profile.risk_score

        second = update_all_profiles(db)  # re-run with no new events
        db.refresh(profile)

        assert first["events_processed"] > 0
        assert second["events_processed"] == 0
        assert profile.risk_score == score_after_first_run  # unchanged, not doubled

    def test_batch_update_works_under_autoflush_false(self):
        """Regression test for a real bug found running this against the
        project's actual reseeded data: seed.py-style scripts use
        autoflush=False sessions, under which a naive per-event
        query-then-create approach cannot see a same-entity profile it just
        created earlier in the same batch (unflushed), so it creates it
        again -- and the eventual bulk insert violates the entity_id primary
        key. Many events for the same new entity in one batch, committed
        once at the end, is exactly the shape that triggered it."""
        db = _fresh_db(autoflush=False)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(30):
            _mk_event(db, now + timedelta(minutes=i), "10.9.9.9", dest_ip="10.0.0.1", dest_port=443)
        db.commit()  # events land as real committed rows, same as seed.py's own per-corpus commits

        # update_all_profiles itself commits only once at the end, after
        # creating/updating potentially many profiles in-session -- this is
        # the shape (many db.add()s before a single commit, under
        # autoflush=False) that triggered the original bug.
        result = update_all_profiles(db)

        assert result["events_processed"] == 30
        assert db.query(EntityProfile).filter(EntityProfile.entity_id == "10.9.9.9").count() == 1

    def test_risk_score_never_exceeds_the_cap(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(MIN_BASELINE_EVENTS + 1):
            _mk_event(db, now + timedelta(minutes=i), "10.1.1.5", dest_ip="10.0.0.1", dest_port=443)
        db.commit()
        update_all_profiles(db)

        # Many spaced-out new ports, enough to blow past a naive unbounded sum.
        for i in range(50):
            _mk_event(db, now + timedelta(hours=i + 1), "10.1.1.5", dest_ip="10.0.0.1", dest_port=2000 + i)
        db.commit()
        update_all_profiles(db)

        profile = db.query(EntityProfile).filter(EntityProfile.entity_id == "10.1.1.5").first()
        assert profile.risk_score <= 100
