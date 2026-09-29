r"""Source contract fingerprinting / drift detection (ULPF-master-prompt.md
C2: "a changed structure marks the source 'Format changed' and requires
review before its events are exported").

A source's "fingerprint" here is the set of field names its real events
actually populate -- both the named canonical fields (source_ip, severity,
...) and whatever landed in `unmapped` (see app/core/processing.py). A real
vendor silently changing their log format (renaming a field, adding a new
one the current mapping doesn't recognize) shows up as this set changing,
without needing a hand-maintained schema per vendor.

The first observation of a source becomes its baseline (no drift, nothing
to compare against yet). After that, drift is measured as Jaccard
similarity between the current sample's field set and the stored baseline;
below `SIMILARITY_THRESHOLD`, the source is flagged `drift_detected=True`
and its baseline is *not* silently updated -- an operator must review and
approve the new fingerprint (`approve_new_fingerprint`) before it replaces
the old one, matching C2's "requires review before its events are exported."
"""
from collections import Counter

from sqlalchemy.orm import Session

from app.models.all import AuditLog, NormalizedEvent, SourceFingerprint

SIMILARITY_THRESHOLD = 0.85
# Real finding (scripts/demo_flow.py's live run): a single renamed field
# among ~9 total fields is still 0.8 Jaccard similarity -- a threshold of
# 0.7 is tuned for a much larger format overhaul, not the realistic "vendor
# renamed one field in a firmware update" scenario this feature exists to
# catch. 0.85 catches a single-field change without needing every field to
# change, while still tolerating a merely-optional field that only
# sometimes appears (that's filtered out by the 20% inclusion rule below,
# before it ever reaches this comparison).
SAMPLE_SIZE = 50


def _field_set_for_event(event: NormalizedEvent) -> set:
    fields = set()
    for name in ("source_ip", "dest_ip", "source_port", "dest_port", "network_protocol", "user_name", "device_vendor", "device_product"):
        if getattr(event, name, None):
            fields.add(name)
    canonical = event.canonical_json or {}
    unmapped = canonical.get("unmapped") or {}
    fields.update(f"unmapped.{k}" for k in unmapped.keys())
    return fields


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def check_source_drift(db: Session, source_id: str = None) -> dict:
    """Checks one source (or every source with events, if source_id is
    None) for drift against its stored fingerprint. Creates a baseline on
    first observation; flags -- but does not silently rebaseline -- on
    subsequent divergence."""
    query = db.query(NormalizedEvent.source_id).filter(NormalizedEvent.source_id.isnot(None)).distinct()
    source_ids = [source_id] if source_id else [r[0] for r in query.all()]

    results = {}
    for sid in source_ids:
        events = (
            db.query(NormalizedEvent)
            .filter(NormalizedEvent.source_id == sid)
            .order_by(NormalizedEvent.timestamp.desc())
            .limit(SAMPLE_SIZE)
            .all()
        )
        if not events:
            continue

        field_counter = Counter()
        for e in events:
            field_counter.update(_field_set_for_event(e))
        # A field only present in a small minority of the sample is noise,
        # not part of the source's actual contract -- require it in at
        # least 20% of sampled events to count.
        current_fields = sorted(f for f, count in field_counter.items() if count >= max(1, len(events) * 0.2))

        existing = db.query(SourceFingerprint).filter(SourceFingerprint.source_id == sid).first()
        if not existing:
            db.add(SourceFingerprint(source_id=sid, field_names=current_fields, sample_count=len(events)))
            db.commit()
            results[sid] = {"status": "baseline_created", "field_names": current_fields}
            continue

        similarity = _jaccard(set(existing.field_names), set(current_fields))
        if similarity < SIMILARITY_THRESHOLD:
            added = sorted(set(current_fields) - set(existing.field_names))
            removed = sorted(set(existing.field_names) - set(current_fields))
            existing.drift_detected = True
            existing.drift_detail = {"added": added, "removed": removed, "similarity": round(similarity, 3), "candidate_fields": current_fields}
            db.commit()
            db.add(AuditLog(
                user="system", action="source_drift_detected", entity_type="Source", entity_id=sid,
                after_state=existing.drift_detail,
            ))
            db.commit()
            results[sid] = {"status": "drift_detected", **existing.drift_detail}
        else:
            results[sid] = {"status": "stable", "similarity": round(similarity, 3)}

    return results


def approve_new_fingerprint(db: Session, source_id: str, approved_by: str) -> SourceFingerprint:
    """An operator's explicit approval of a drifted source's new shape as
    the go-forward baseline -- the "review" C2 requires before treating the
    new format as normal, not an auto-heal."""
    fp = db.query(SourceFingerprint).filter(SourceFingerprint.source_id == source_id).first()
    if not fp or not fp.drift_detected:
        return fp
    new_fields = (fp.drift_detail or {}).get("candidate_fields", fp.field_names)
    fp.field_names = new_fields
    fp.drift_detected = False
    fp.drift_detail = None
    db.commit()
    db.refresh(fp)
    db.add(AuditLog(user=approved_by, action="source_drift_approved", entity_type="Source", entity_id=source_id,
                     after_state={"new_field_names": new_fields}))
    db.commit()
    return fp
