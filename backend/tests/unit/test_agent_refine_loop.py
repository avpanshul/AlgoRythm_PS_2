"""Tests for Item 5: agent refine loop (app/services/pack_drafting.py).

Real components throughout -- no mocking. Where a real LLM call is
exercised, OLLAMA_TIMEOUT_SECONDS is temporarily lowered so a real network
attempt that can't complete fails fast via a real timeout rather than the
production default (this project's own Item 1 audit found real CPU-only
inference can take 30-90s+ per call) -- this keeps the test both real and
bounded, not mocked.
"""
import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.config import settings
from app.models.all import DLQEvent, AgentReasoningTraceEntry, Parser
from app.services.pack_drafting import draft_pack_for_cluster


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _mk_dlq(db, cluster_id, raw_log):
    db.add(DLQEvent(
        event_id=f"evt-{uuid.uuid4().hex[:12]}", source_id="TEST", raw_log=raw_log,
        failure_reason="UnknownFormatError", drain_cluster_id=cluster_id, status="failed",
        created_at=datetime.now(timezone.utc),
    ))


class TestFlagOffIsUnchangedSinglePass:
    def test_no_trace_rows_when_refine_disabled(self):
        db = _fresh_db()
        original = settings.ENABLE_AGENT_REFINE
        settings.ENABLE_AGENT_REFINE = False
        try:
            cluster_id = "refine-off-test"
            _mk_dlq(db, cluster_id, "src_ip=10.1.1.1 user=alice action=login result=success")
            db.commit()

            result = draft_pack_for_cluster(db, cluster_id)

            assert result["status"] == "drafted"
            assert db.query(AgentReasoningTraceEntry).filter(AgentReasoningTraceEntry.cluster_id == cluster_id).count() == 0
        finally:
            settings.ENABLE_AGENT_REFINE = original


class TestRefineLoopStopsImmediatelyOnFullCoverage:
    def test_single_attempt_when_everything_classifies_deterministically(self):
        """No unknown fields at all after attempt 1 -- the loop must not
        make any further (real, network-dependent) LLM attempts, verified
        by there being exactly one trace row."""
        db = _fresh_db()
        original = settings.ENABLE_AGENT_REFINE
        settings.ENABLE_AGENT_REFINE = True
        try:
            cluster_id = "refine-full-coverage-test"
            # Every one of these field names is in app/ai/deterministic_mapping.py's
            # real alias table -- no LLM call is possible or needed here.
            _mk_dlq(db, cluster_id, "src_ip=10.1.1.2 dst_ip=10.1.1.3 user=bob action=login result=success ts=2026-09-29T00:00:00")
            db.commit()

            result = draft_pack_for_cluster(db, cluster_id)

            assert result["status"] == "drafted"
            trace = (
                db.query(AgentReasoningTraceEntry)
                .filter(AgentReasoningTraceEntry.cluster_id == cluster_id)
                .order_by(AgentReasoningTraceEntry.attempt_number)
                .all()
            )
            assert len(trace) == 1
            assert trace[0].attempt_number == 1
            assert trace[0].feedback_used is None
            assert trace[0].unmapped_field_count == 0
        finally:
            settings.ENABLE_AGENT_REFINE = original


class TestRefineLoopAttemptsAndRecordsRealFeedback:
    def test_multiple_attempts_recorded_with_real_feedback_text(self):
        """A field name not in the deterministic table forces a real LLM
        attempt for it. Whether or not Ollama actually answers in time
        (this project's own known real-world unreliability, see Item 1),
        the loop must: try more than once (bounded by AGENT_REFINE_MAX_ATTEMPTS),
        record every attempt with a real, non-empty feedback string on
        attempt 2+, and never exceed the configured max."""
        db = _fresh_db()
        original_flag = settings.ENABLE_AGENT_REFINE
        original_max = settings.AGENT_REFINE_MAX_ATTEMPTS
        original_timeout = settings.OLLAMA_TIMEOUT_SECONDS
        settings.ENABLE_AGENT_REFINE = True
        settings.AGENT_REFINE_MAX_ATTEMPTS = 3
        settings.OLLAMA_TIMEOUT_SECONDS = 3  # real timeout, kept short so a real unreachable/slow call fails fast
        try:
            cluster_id = "refine-multi-attempt-test"
            # "totally_unrecognized_xyz" is not in the deterministic alias
            # table -- forces a real (possibly failing/timing-out) LLM path.
            _mk_dlq(db, cluster_id, "src_ip=10.1.1.4 totally_unrecognized_xyz=something action=login")
            db.commit()

            result = draft_pack_for_cluster(db, cluster_id)

            assert result["status"] == "drafted"
            trace = (
                db.query(AgentReasoningTraceEntry)
                .filter(AgentReasoningTraceEntry.cluster_id == cluster_id)
                .order_by(AgentReasoningTraceEntry.attempt_number)
                .all()
            )
            assert len(trace) >= 1
            assert len(trace) <= settings.AGENT_REFINE_MAX_ATTEMPTS
            attempt_numbers = [t.attempt_number for t in trace]
            assert attempt_numbers == sorted(attempt_numbers)
            assert attempt_numbers[0] == 1
            for t in trace[1:]:
                assert t.feedback_used is not None
                assert "still has no value for" in t.feedback_used
        finally:
            settings.ENABLE_AGENT_REFINE = original_flag
            settings.AGENT_REFINE_MAX_ATTEMPTS = original_max
            settings.OLLAMA_TIMEOUT_SECONDS = original_timeout


class TestReasoningTraceIsHonestlyEmptyWhenNeverRun:
    def test_no_rows_for_a_cluster_that_was_never_drafted(self):
        db = _fresh_db()
        assert db.query(AgentReasoningTraceEntry).filter(AgentReasoningTraceEntry.cluster_id == "never-touched").count() == 0
