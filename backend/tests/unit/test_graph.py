"""Tests for the entity graph and attack-path reconstruction
(ULPF-phase2-prompt.md E2/E8). Hand-constructed events -- test fixtures for
exercising graph-building logic, same category as the correlation-engine
and Sentinel tests.
"""
import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.all import NormalizedEvent, EntityProfile, CorrelatedIncident
from app.analytics.graph import build_graph, reconstruct_attack_path, build_timeline


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _mk_event(db, ts, source_ip, dest_ip, correlation_id=None):
    eid = f"evt-{uuid.uuid4().hex[:12]}"
    db.add(NormalizedEvent(
        event_id=eid, timestamp=ts, source_ip=source_ip, dest_ip=dest_ip,
        correlation_id=correlation_id, event_data={"category": "network"},
    ))
    return eid


class TestBuildGraph:
    def test_nodes_and_edges_reflect_real_events(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _mk_event(db, now, "10.0.0.1", "10.0.0.2")
        _mk_event(db, now + timedelta(minutes=1), "10.0.0.1", "10.0.0.2")
        _mk_event(db, now + timedelta(minutes=2), "10.0.0.2", "10.0.0.3")
        db.commit()

        graph = build_graph(db)
        node_ids = {n["id"] for n in graph["nodes"]}
        assert node_ids == {"10.0.0.1", "10.0.0.2", "10.0.0.3"}

        edge = next(e for e in graph["edges"] if e["source"] == "10.0.0.1" and e["target"] == "10.0.0.2")
        assert edge["weight"] == 2  # two real events between the same pair

    def test_correlation_id_is_attached_to_matching_edges(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _mk_event(db, now, "10.0.0.1", "10.0.0.2", correlation_id="corr-abc")
        db.commit()

        graph = build_graph(db)
        edge = next(e for e in graph["edges"] if e["source"] == "10.0.0.1")
        assert "corr-abc" in edge["correlation_ids"]

    def test_risk_score_attached_from_real_sentinel_profile(self):
        db = _fresh_db()
        db.add(EntityProfile(entity_id="10.0.0.1", risk_score=42.0, event_count=10))
        db.commit()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _mk_event(db, now, "10.0.0.1", "10.0.0.2")
        db.commit()

        graph = build_graph(db)
        node = next(n for n in graph["nodes"] if n["id"] == "10.0.0.1")
        assert node["risk_score"] == 42.0

    def test_pivot_by_entity_returns_only_its_neighborhood(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _mk_event(db, now, "10.0.0.1", "10.0.0.2")
        _mk_event(db, now, "10.0.0.9", "10.0.0.8")  # unrelated pair
        db.commit()

        graph = build_graph(db, entity="10.0.0.1")
        node_ids = {n["id"] for n in graph["nodes"]}
        assert node_ids == {"10.0.0.1", "10.0.0.2"}
        assert "10.0.0.9" not in node_ids


class TestAttackPath:
    def test_reconstructs_a_real_multi_hop_chain_in_time_order(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _mk_event(db, now, "10.0.0.1", "10.0.0.2")
        _mk_event(db, now + timedelta(minutes=10), "10.0.0.2", "10.0.0.3")
        _mk_event(db, now + timedelta(minutes=20), "10.0.0.3", "10.0.0.4")
        db.commit()

        result = reconstruct_attack_path(db, entity="10.0.0.1")
        hops = [(h["from"], h["to"]) for h in result["path"]]
        assert hops == [("10.0.0.1", "10.0.0.2"), ("10.0.0.2", "10.0.0.3"), ("10.0.0.3", "10.0.0.4")]
        assert result["front"] == "10.0.0.4"

    def test_does_not_hop_backward_in_time(self):
        """A real edge that happened *before* the front arrived there isn't
        a legitimate next hop -- proves the reconstruction is genuinely
        time-ordered, not just graph-connected."""
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _mk_event(db, now + timedelta(minutes=10), "10.0.0.1", "10.0.0.2")
        # This edge from 10.0.0.2 happened *before* 10.0.0.1 even reached it.
        _mk_event(db, now, "10.0.0.2", "10.0.0.3")
        db.commit()

        result = reconstruct_attack_path(db, entity="10.0.0.1")
        hops = [(h["from"], h["to"]) for h in result["path"]]
        assert ("10.0.0.2", "10.0.0.3") not in hops

    def test_proximity_watchlist_is_same_subnet_not_yet_visited(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _mk_event(db, now, "10.0.0.1", "10.0.0.2")
        _mk_event(db, now, "10.0.0.50", "10.0.0.51")  # same /24 as the front, unvisited
        _mk_event(db, now, "192.168.1.1", "192.168.1.2")  # different subnet entirely
        db.commit()

        result = reconstruct_attack_path(db, entity="10.0.0.1")
        assert "10.0.0.50" in result["proximity_watchlist"] or "10.0.0.51" in result["proximity_watchlist"]
        assert "192.168.1.1" not in result["proximity_watchlist"]
        assert "192.168.1.2" not in result["proximity_watchlist"]

    def test_never_claims_prediction_in_its_own_output(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _mk_event(db, now, "10.0.0.1", "10.0.0.2")
        db.commit()
        result = reconstruct_attack_path(db, entity="10.0.0.1")
        assert "predict" not in result["proximity_note"].lower()


class TestTimeline:
    def test_entity_mode_returns_chronological_real_events(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        e3 = _mk_event(db, now + timedelta(minutes=20), "10.0.0.1", "10.0.0.9")
        e1 = _mk_event(db, now, "10.0.0.1", "10.0.0.2")
        e2 = _mk_event(db, now + timedelta(minutes=10), "10.0.0.5", "10.0.0.1")
        db.commit()

        result = build_timeline(db, entity="10.0.0.1")
        assert result["mode"] == "entity"
        ids = [e["event_id"] for e in result["events"]]
        assert ids == [e1, e2, e3]  # strictly time-ordered

    def test_entity_mode_matches_source_dest_or_user(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.add(NormalizedEvent(
            event_id="evt-user", timestamp=now, source_ip="10.9.9.9", dest_ip="10.9.9.8",
            user_name="alice", event_data={"category": "auth"},
        ))
        db.commit()

        result = build_timeline(db, entity="alice")
        assert len(result["events"]) == 1
        assert result["events"][0]["event_id"] == "evt-user"

    def test_entity_with_no_events_is_an_honest_empty_list(self):
        db = _fresh_db()
        result = build_timeline(db, entity="10.255.255.255")
        assert result["events"] == []

    def test_incident_mode_returns_exactly_the_incidents_own_event_set_in_order(self):
        db = _fresh_db()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        e1 = _mk_event(db, now + timedelta(minutes=5), "10.0.0.1", "10.0.0.2")
        e2 = _mk_event(db, now, "10.0.0.1", "10.0.0.3")
        _mk_event(db, now, "10.0.0.9", "10.0.0.8")  # not part of the incident
        db.add(CorrelatedIncident(
            id="corr-xyz", rule_id="rule-1", rule_name="Test Rule", correlate_key="10.0.0.1",
            event_ids=[e1, e2], distinct_source_count=1,
            first_event_at=now, last_event_at=now + timedelta(minutes=5),
        ))
        db.commit()

        result = build_timeline(db, incident_id="corr-xyz")
        assert result["mode"] == "incident"
        assert result["found"] is True
        assert result["rule_name"] == "Test Rule"
        ids = [e["event_id"] for e in result["events"]]
        assert ids == [e2, e1]  # time-ordered, not insertion-ordered

    def test_unknown_incident_id_is_honestly_reported_not_found(self):
        db = _fresh_db()
        result = build_timeline(db, incident_id="does-not-exist")
        assert result["found"] is False
        assert result["events"] == []

    def test_neither_entity_nor_incident_given_is_an_explicit_error_not_a_silent_empty(self):
        db = _fresh_db()
        result = build_timeline(db)
        assert result["events"] == []
        assert "error" in result
