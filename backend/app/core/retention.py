r"""Retention and legal hold (ULPF-master-prompt.md D10).

Deletes NormalizedEvent + RawEventMetadata + the physical raw-vault file for
events past a source's retention_days, unless an active LegalHold covers
that source. Deliberately never touches the Merkle leaf: a leaf is just a
hash, not content, so the tree and every checkpoint over it remain provable
after the event's own content is gone -- "prove an event with this hash
existed in this tree at this time" and "retain this event's content
forever" are different guarantees, and D10 is explicitly about the second
one, not the first.

Every deletion is recorded in the existing hash-chained AuditLog
(app/models/all.py's before_insert listener, Part D5) -- that chain is what
makes a deletion record "signed" here: tamper-evident by construction,
without inventing a second, redundant signature scheme alongside the
checkpoint one that already exists for a different purpose (proving event
content, not proving deletion history).
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.local_storage import delete_raw_log
from app.models.all import AuditLog, LegalHold, NormalizedEvent, RawEventMetadata, RetentionPolicy


def _active_hold(db: Session, source_id: str) -> LegalHold:
    return (
        db.query(LegalHold)
        .filter(LegalHold.source_id == source_id, LegalHold.released_at.is_(None))
        .first()
    )


def place_hold(db: Session, source_id: str, reason: str, created_by: str) -> LegalHold:
    hold = LegalHold(id=f"hold-{uuid.uuid4().hex[:16]}", source_id=source_id, reason=reason, created_by=created_by)
    db.add(hold)
    db.commit()
    db.refresh(hold)
    db.add(AuditLog(user=created_by, action="legal_hold_placed", entity_type="Source", entity_id=source_id,
                     after_state={"hold_id": hold.id, "reason": reason}))
    db.commit()
    return hold


def release_hold(db: Session, hold_id: str, released_by: str) -> LegalHold:
    hold = db.query(LegalHold).filter(LegalHold.id == hold_id).first()
    if not hold or hold.released_at:
        return hold
    hold.released_at = datetime.now(timezone.utc)
    hold.released_by = released_by
    db.commit()
    db.refresh(hold)
    db.add(AuditLog(user=released_by, action="legal_hold_released", entity_type="Source", entity_id=hold.source_id,
                     after_state={"hold_id": hold.id}))
    db.commit()
    return hold


def delete_event(db: Session, event_id: str, deleted_by: str) -> dict:
    """Single-event delete, respecting legal holds. Exists specifically so
    "an attempted delete of a held event is blocked and logged" (D10's own
    acceptance criterion) is a real, callable, tested code path -- not just
    an implicit side effect of the batch sweep skipping held sources."""
    event = db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).first()
    if not event:
        return {"status": "not_found"}

    hold = _active_hold(db, event.source_id) if event.source_id else None
    if hold:
        db.add(AuditLog(
            user=deleted_by, action="event_delete_blocked_by_legal_hold", entity_type="NormalizedEvent",
            entity_id=event_id, reason=f"source {event.source_id} is under legal hold {hold.id}: {hold.reason}",
        ))
        db.commit()
        return {"status": "blocked", "reason": f"source under legal hold: {hold.reason}", "hold_id": hold.id}

    return _delete_one(db, event, deleted_by, reason="manual_delete")


def _delete_one(db: Session, event: NormalizedEvent, actor: str, reason: str) -> dict:
    raw_sha256 = event.raw_sha256
    source_id = event.source_id
    meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == event.event_id).first()
    raw_location = meta.raw_location if meta else None

    file_deleted = delete_raw_log(raw_location) if raw_location else False
    if meta:
        db.delete(meta)
    db.delete(event)

    # The signed (hash-chained) deletion record -- kept even though the
    # event and its raw content are both gone, which is the whole point:
    # this row is the durable proof that a deletion happened, why, and by
    # whom, independent of whatever was deleted.
    db.add(AuditLog(
        user=actor, action="event_deleted", entity_type="NormalizedEvent", entity_id=event.event_id,
        reason=reason,
        after_state={"source_id": source_id, "raw_sha256": raw_sha256, "raw_file_deleted": file_deleted},
    ))
    db.commit()
    return {"status": "deleted", "raw_file_deleted": file_deleted}


def run_retention_sweep(db: Session) -> dict:
    """Batch sweep: for every enabled RetentionPolicy, deletes that source's
    events older than retention_days, skipping any source currently under
    legal hold entirely (not per-event -- a hold protects the whole source,
    per the master prompt's own LegalHold{source_id, reason} shape).
    Callable on demand or from a scheduler -- same on-demand-batch pattern
    as correlation/sentinel/notification escalation elsewhere in this
    project."""
    now = datetime.now(timezone.utc)
    policies = db.query(RetentionPolicy).filter(RetentionPolicy.enabled.is_(True)).all()

    results = {}
    for policy in policies:
        hold = _active_hold(db, policy.source_id)
        if hold:
            results[policy.source_id] = {"skipped": True, "reason": f"under legal hold {hold.id}"}
            continue

        cutoff = now - timedelta(days=policy.retention_days)
        expired = db.query(NormalizedEvent).filter(
            NormalizedEvent.source_id == policy.source_id, NormalizedEvent.timestamp < cutoff,
        ).all()

        deleted = 0
        for event in expired:
            _delete_one(db, event, actor="system", reason=f"retention_policy_expired (>{policy.retention_days}d)")
            deleted += 1
        results[policy.source_id] = {"deleted": deleted, "retention_days": policy.retention_days}

    return results
