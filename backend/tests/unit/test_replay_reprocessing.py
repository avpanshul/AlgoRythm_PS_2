"""Regression test for a real bug found live (2026-09-29): replaying an
already-ingested event through process_raw_event() a second time always
failed with a real `UNIQUE constraint failed` -- first on merkle_leaves,
then (once that was fixed) on normalized_events -- because both paths
unconditionally INSERTed instead of handling "this event_id already exists."
Every event a real Replay job touched was spuriously dumped into the DLQ
even though nothing was wrong with it.

Real process_raw_event() calls against a real in-memory DB + real raw-log
files, per this project's no-mocking rule -- not stubbed.
"""
import sys
import os
import hashlib
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.local_storage import save_raw_log
from app.core.processing import process_raw_event
from app.models.all import NormalizedEvent, MerkleLeaf, DLQEvent, RawEventMetadata


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _ingest(db, raw_log: str, source_id: str = "TEST"):
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    raw_sha256 = hashlib.sha256(raw_log.encode("utf-8")).hexdigest()
    raw_location = f"replay_test/{event_id}.txt"
    save_raw_log(raw_location, raw_log)
    db.add(RawEventMetadata(event_id=event_id, source_id=source_id, ingestion_protocol="test", raw_sha256=raw_sha256, raw_location=raw_location, processing_status="processing"))
    db.commit()
    result = process_raw_event(db, event_id, raw_log, source_id, raw_sha256, raw_location)
    return event_id, raw_log, raw_sha256, raw_location, result


class TestReplayDoesNotDuplicateMerkleLeaf:
    def test_reprocessing_the_same_event_id_succeeds_not_dlq(self):
        db = _fresh_db()
        raw = "src_ip=10.5.5.1 user=alice action=login result=success"
        event_id, raw_log, raw_sha256, raw_location, first_result = _ingest(db, raw)
        assert first_result is not None, "initial ingest must succeed for this test to be meaningful"

        # Simulate a real Replay job: re-run the same raw content through the
        # same event_id, as app/api/v1/replay.py does.
        second_result = process_raw_event(db, event_id, raw_log, "TEST", raw_sha256, raw_location)

        assert second_result is not None, "replay of an already-ingested event must succeed, not fail into DLQ"
        assert db.query(DLQEvent).filter(DLQEvent.event_id == event_id).count() == 0

    def test_merkle_leaf_is_not_duplicated_or_changed_by_replay(self):
        db = _fresh_db()
        raw = "src_ip=10.5.5.2 user=bob action=login result=success"
        event_id, raw_log, raw_sha256, raw_location, _ = _ingest(db, raw)

        leaf_before = db.query(MerkleLeaf).filter(MerkleLeaf.event_id == event_id).first()
        assert leaf_before is not None

        process_raw_event(db, event_id, raw_log, "TEST", raw_sha256, raw_location)

        leaves = db.query(MerkleLeaf).filter(MerkleLeaf.event_id == event_id).all()
        assert len(leaves) == 1, "replay must never create a second leaf for the same event_id"
        assert leaves[0].leaf_hash == leaf_before.leaf_hash, "an existing leaf's hash must never change -- that's the actual tamper-evidence property"
        assert leaves[0].sequence == leaf_before.sequence

    def test_normalized_event_is_updated_in_place_not_duplicated(self):
        db = _fresh_db()
        raw = "src_ip=10.5.5.3 user=carol action=login result=success"
        event_id, raw_log, raw_sha256, raw_location, _ = _ingest(db, raw)

        # A real replay with a *different* parser could change the normalized
        # content (that's the whole point of replay) -- simulate that with a
        # genuinely different raw line reprocessed under the same event_id.
        new_raw = "src_ip=10.5.5.3 user=carol action=logout result=success"
        process_raw_event(db, event_id, new_raw, "TEST", raw_sha256, raw_location)

        rows = db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).all()
        assert len(rows) == 1, "replay must update the existing NormalizedEvent row, never insert a second one"
        assert rows[0].message == new_raw or "logout" in (rows[0].message or ""), "the updated content should reflect the replayed input"

    def test_leaf_lookup_returns_the_existing_row_unmodified(self):
        """Direct unit test of the fixed append_leaf() itself."""
        from app.integrity import service as integrity_service

        db = _fresh_db()
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        first = integrity_service.append_leaf(db, event_id, "sha-a")
        db.commit()
        second = integrity_service.append_leaf(db, event_id, "sha-b")  # different normalized_sha256, as a real content change would produce
        db.commit()

        assert first.leaf_hash == second.leaf_hash, "append_leaf must return the ORIGINAL leaf unchanged, never recompute it from new content"
        assert db.query(MerkleLeaf).filter(MerkleLeaf.event_id == event_id).count() == 1
