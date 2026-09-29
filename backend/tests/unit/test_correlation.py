"""Tests for the correlation engine (ULPF-phase2-prompt.md E1).

Uses hand-constructed NormalizedEvent rows in an in-memory DB -- test
fixtures for exercising rule-matching logic, the same category as the
Merkle tests' `f"item-{i}".encode()` leaves, not a claim about real traffic.
No product surface (dashboard, seeded demo data) is touched by this file.
"""
import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.all import NormalizedEvent, CorrelatedIncident, Source
from app.analytics.correlation import evaluate_rule, load_rules


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _mk_event(db, ts, source_id, source_ip, action, severity="info", dest_port=None):
    eid = f"evt-{uuid.uuid4().hex[:12]}"
    db.add(NormalizedEvent(
        event_id=eid, timestamp=ts, source_id=source_id,
        source_ip=source_ip, dest_port=dest_port, action=action, severity=severity,
        event_data={"category": "network", "action": action, "severity": severity},
    ))
    return eid


def _ensure_sources(db, ids):
    for sid in ids:
        if not db.query(Source).filter(Source.id == sid).first():
            db.add(Source(id=sid, name=sid))
    db.commit()


class TestRuleLoading:
    def test_starter_rules_load_and_are_well_formed(self):
        rules = load_rules()
        ids = {r["id"] for r in rules}
        assert "brute_force_then_lateral_movement" in ids
        assert "recon_then_exploitation" in ids
        assert "privilege_escalation_then_transfer" in ids
        for r in rules:
            assert "window_minutes" in r
            assert "correlate_by" in r
            # Real bug found live (2026-09-29): this asserted every rule has
            # >=2 stages, written back when only the 3 original multi-stage
            # sequence rules existed. ntlm_password_spraying is a real,
            # deliberately single-stage rule (many distinct accounts hit
            # from one source in a window is itself the whole detection --
            # password spraying has no "sequence" to require, unlike
            # brute-force-then-lateral-movement) -- every rule genuinely
            # needs at least one stage, but not necessarily two or more.
            assert "stages" in r and len(r["stages"]) >= 1


class TestBruteForceThenLateralMovement:
    RULE = next(r for r in load_rules() if r["id"] == "brute_force_then_lateral_movement")

    def test_matches_across_two_sources_within_window(self):
        db = _fresh_db()
        _ensure_sources(db, ["FW-1", "IDS-1"])
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # 3 failed logins from FW-1
        for i in range(3):
            _mk_event(db, now + timedelta(minutes=i), "FW-1", "10.0.0.5", "login failed")
        # then a high-severity admin/lateral-movement-shaped event from IDS-1, same IP
        _mk_event(db, now + timedelta(minutes=10), "IDS-1", "10.0.0.5", "admin logon success", severity="high")
        db.commit()

        incidents = evaluate_rule(db, self.RULE, now=now + timedelta(minutes=15))
        db.commit()

        assert len(incidents) == 1
        incident = incidents[0]
        assert incident.distinct_source_count == 2
        assert len(incident.event_ids) == 4

        matched = db.query(NormalizedEvent).filter(NormalizedEvent.correlation_id == incident.id).all()
        assert len(matched) == 4

    def test_does_not_match_from_a_single_source_alone(self):
        """Proves min_distinct_sources is actually enforced, not cosmetic."""
        db = _fresh_db()
        _ensure_sources(db, ["FW-1"])
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(3):
            _mk_event(db, now + timedelta(minutes=i), "FW-1", "10.0.0.6", "login failed")
        _mk_event(db, now + timedelta(minutes=10), "FW-1", "10.0.0.6", "admin logon success", severity="high")
        db.commit()

        incidents = evaluate_rule(db, self.RULE, now=now + timedelta(minutes=15))
        assert incidents == []

    def test_does_not_match_when_lateral_movement_precedes_brute_force(self):
        """Proves the `after` ordering constraint is enforced, not just
        co-occurrence within the window."""
        db = _fresh_db()
        _ensure_sources(db, ["FW-1", "IDS-1"])
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _mk_event(db, now, "IDS-1", "10.0.0.7", "admin logon success", severity="high")
        for i in range(3):
            _mk_event(db, now + timedelta(minutes=i + 1), "FW-1", "10.0.0.7", "login failed")
        db.commit()

        incidents = evaluate_rule(db, self.RULE, now=now + timedelta(minutes=15))
        assert incidents == []

    def test_does_not_match_outside_the_time_window(self):
        db = _fresh_db()
        _ensure_sources(db, ["FW-1", "IDS-1"])
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(3):
            _mk_event(db, now + timedelta(minutes=i), "FW-1", "10.0.0.8", "login failed")
        # lateral movement event is far outside the rule's 30-minute window
        _mk_event(db, now + timedelta(hours=5), "IDS-1", "10.0.0.8", "admin logon success", severity="high")
        db.commit()

        incidents = evaluate_rule(db, self.RULE, now=now + timedelta(hours=5, minutes=1))
        assert incidents == []

    def test_reevaluation_does_not_duplicate_the_same_incident(self):
        db = _fresh_db()
        _ensure_sources(db, ["FW-1", "IDS-1"])
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(3):
            _mk_event(db, now + timedelta(minutes=i), "FW-1", "10.0.0.9", "login failed")
        _mk_event(db, now + timedelta(minutes=10), "IDS-1", "10.0.0.9", "admin logon success", severity="high")
        db.commit()

        first = evaluate_rule(db, self.RULE, now=now + timedelta(minutes=15))
        db.commit()
        second = evaluate_rule(db, self.RULE, now=now + timedelta(minutes=16))
        db.commit()

        assert len(first) == 1
        assert len(second) == 0
        assert db.query(CorrelatedIncident).count() == 1


class TestReconThenExploitation:
    RULE = next(r for r in load_rules() if r["id"] == "recon_then_exploitation")

    def test_port_scan_shape_then_high_severity_hit_matches(self):
        db = _fresh_db()
        _ensure_sources(db, ["FW-1"])
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i, port in enumerate([22, 80, 443, 3389, 8080]):
            _mk_event(db, now + timedelta(minutes=i), "FW-1", "10.0.0.10", "probe", dest_port=port)
        _mk_event(db, now + timedelta(minutes=10), "FW-1", "10.0.0.10", "exploit attempt", severity="critical")
        db.commit()

        incidents = evaluate_rule(db, self.RULE, now=now + timedelta(minutes=15))
        assert len(incidents) == 1

    def test_few_distinct_ports_does_not_match(self):
        db = _fresh_db()
        _ensure_sources(db, ["FW-1"])
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(5):
            _mk_event(db, now + timedelta(minutes=i), "FW-1", "10.0.0.11", "probe", dest_port=80)  # same port every time
        _mk_event(db, now + timedelta(minutes=10), "FW-1", "10.0.0.11", "exploit attempt", severity="critical")
        db.commit()

        incidents = evaluate_rule(db, self.RULE, now=now + timedelta(minutes=15))
        assert incidents == []
