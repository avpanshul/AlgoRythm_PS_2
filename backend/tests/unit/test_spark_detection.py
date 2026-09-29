"""Tests for Item 2: spark detection (app/services/spark_detection.py).

Hand-constructed fixtures in an in-memory DB, same pattern as
test_correlation.py -- not a claim about real traffic.
"""
import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.config import settings
from app.models.all import NormalizedEvent, CorrelatedIncident, EntityProfile, Spark
from app.services.spark_detection import (
    run_spark_detection, detect_sparks_from_new_incidents, detect_sparks_from_risk_threshold,
)


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _mk_event(db, ts, source_ip, event_id=None):
    eid = event_id or f"evt-{uuid.uuid4().hex[:12]}"
    db.add(NormalizedEvent(event_id=eid, timestamp=ts, source_ip=source_ip, event_data={}))
    return eid


def _mk_incident(db, event_ids, rule_id="test_rule", rule_name="Test Rule", correlate_key="1.2.3.4"):
    now = datetime.now(timezone.utc)
    incident = CorrelatedIncident(
        id=f"corr-{uuid.uuid4().hex[:16]}", rule_id=rule_id, rule_name=rule_name,
        correlate_key=correlate_key, event_ids=event_ids, distinct_source_count=1,
        first_event_at=now - timedelta(minutes=5), last_event_at=now,
    )
    db.add(incident)
    db.commit()
    return incident


class TestFlagOff:
    def test_disabled_by_default_creates_nothing(self):
        db = _fresh_db()
        original = settings.ENABLE_SPARK_DETECTION
        settings.ENABLE_SPARK_DETECTION = False
        try:
            result = run_spark_detection(db, [])
            assert result["enabled"] is False
            assert result["sparks_created"] == 0
            assert db.query(Spark).count() == 0
        finally:
            settings.ENABLE_SPARK_DETECTION = original


class TestCorrelatedIncidentTrigger:
    def test_spark_created_from_new_incident_with_real_reason(self):
        db = _fresh_db()
        ts = datetime.now(timezone.utc) - timedelta(minutes=10)
        eid = _mk_event(db, ts, "10.0.0.5")
        db.commit()
        incident = _mk_incident(db, [eid])

        sparks = detect_sparks_from_new_incidents(db, [incident.id])
        db.commit()

        assert len(sparks) == 1
        spark = sparks[0]
        assert spark.entity == "10.0.0.5"
        assert spark.trigger_type == "correlated_incident"
        assert spark.source_incident_id == incident.id
        assert "Test Rule" in spark.reason
        assert incident.rule_id in spark.reason

    def test_no_duplicate_spark_for_the_same_incident(self):
        db = _fresh_db()
        eid = _mk_event(db, datetime.now(timezone.utc), "10.0.0.6")
        db.commit()
        incident = _mk_incident(db, [eid])

        first = detect_sparks_from_new_incidents(db, [incident.id])
        db.commit()
        second = detect_sparks_from_new_incidents(db, [incident.id])
        db.commit()

        assert len(first) == 1
        assert len(second) == 0
        assert db.query(Spark).filter(Spark.source_incident_id == incident.id).count() == 1

    def test_incident_with_no_events_is_skipped_honestly(self):
        db = _fresh_db()
        incident = _mk_incident(db, [])
        sparks = detect_sparks_from_new_incidents(db, [incident.id])
        assert sparks == []


class TestRiskThresholdTrigger:
    def test_spark_created_when_risk_crosses_threshold(self):
        db = _fresh_db()
        original = settings.SPARK_RISK_THRESHOLD
        settings.SPARK_RISK_THRESHOLD = 80.0
        try:
            db.add(EntityProfile(entity_id="10.0.0.9", risk_score=85.0))
            db.commit()
            sparks = detect_sparks_from_risk_threshold(db)
            db.commit()
            assert len(sparks) == 1
            assert sparks[0].entity == "10.0.0.9"
            assert sparks[0].trigger_type == "risk_threshold"
            assert sparks[0].risk_score == 85.0
        finally:
            settings.SPARK_RISK_THRESHOLD = original

    def test_below_threshold_no_spark(self):
        db = _fresh_db()
        original = settings.SPARK_RISK_THRESHOLD
        settings.SPARK_RISK_THRESHOLD = 80.0
        try:
            db.add(EntityProfile(entity_id="10.0.0.10", risk_score=40.0))
            db.commit()
            sparks = detect_sparks_from_risk_threshold(db)
            assert sparks == []
        finally:
            settings.SPARK_RISK_THRESHOLD = original

    def test_one_spark_per_entity_ever_for_this_trigger(self):
        db = _fresh_db()
        original = settings.SPARK_RISK_THRESHOLD
        settings.SPARK_RISK_THRESHOLD = 80.0
        try:
            db.add(EntityProfile(entity_id="10.0.0.11", risk_score=90.0))
            db.commit()
            first = detect_sparks_from_risk_threshold(db)
            db.commit()
            second = detect_sparks_from_risk_threshold(db)
            assert len(first) == 1
            assert len(second) == 0
        finally:
            settings.SPARK_RISK_THRESHOLD = original


class TestFullCycleWhenEnabled:
    def test_run_spark_detection_end_to_end(self):
        db = _fresh_db()
        original_flag = settings.ENABLE_SPARK_DETECTION
        original_thresh = settings.SPARK_RISK_THRESHOLD
        settings.ENABLE_SPARK_DETECTION = True
        settings.SPARK_RISK_THRESHOLD = 80.0
        try:
            eid = _mk_event(db, datetime.now(timezone.utc), "10.0.0.20")
            db.commit()
            incident = _mk_incident(db, [eid])
            db.add(EntityProfile(entity_id="10.0.0.21", risk_score=95.0))
            db.commit()

            result = run_spark_detection(db, [incident.id])

            assert result["enabled"] is True
            assert result["sparks_created"] == 2
            assert result["from_correlated_incidents"] == 1
            assert result["from_risk_threshold"] == 1
            assert db.query(Spark).count() == 2
            # every spark has a real path (possibly empty, but never absent)
            for s in db.query(Spark).all():
                assert s.path is not None
                assert s.hop_count == len(s.path)
        finally:
            settings.ENABLE_SPARK_DETECTION = original_flag
            settings.SPARK_RISK_THRESHOLD = original_thresh
