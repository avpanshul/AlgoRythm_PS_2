r"""Persistent per-entity behavioral tracking ("Sentinel", ULPF-phase2-prompt.md
E7a) -- a real, unsupervised baseline built from this project's own real
seeded data, not a trained classifier and not dependent on any "malicious"
ground-truth label (which is exactly the thing docs/ML_EVENT_CLASSIFIER.md
found this project's real data can't honestly supply at the per-event level).

The idea: maintain one profile per entity (currently source_ip; user_name
could be added the same way) that accumulates what "normal" looks like for
*that entity specifically* -- its own ports, protocols, and peers seen so
far -- and scores each new event only against its own history, not against
other entities or an invented label. A port/peer/protocol an entity has
never touched before is "surprising" for that entity regardless of whether
it would be ordinary for some other entity; that is genuinely learnable
from unlabeled real traffic, unlike "is this event malicious."

Every score change is explainable: `reason_log` records exactly what was
new and how much it contributed, so `risk_score` is never a bare number
(the same principle app/core/processing.py:compute_risk_score already
applies to per-event risk -- this extends it to a per-entity running total
that persists and accumulates across many small anomalies instead of
resetting after each event, per E7a's explicit requirement).
"""
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.all import EntityProfile, NormalizedEvent

# Minimum events seen before "never touched this before" is treated as a
# signal -- otherwise every entity's first few events would all look like
# anomalies purely from having no history yet (a cold-start artifact, not a
# real behavioral surprise).
MIN_BASELINE_EVENTS = 5

_CONTRIBUTIONS = {
    "new_dest_port": 5,
    "new_peer": 4,
    "new_protocol": 6,
    "new_severity_high_or_above": 8,
}
MAX_SCORE = 100


def _get_or_create_profile(db: Session, entity_id: str, entity_type: str) -> EntityProfile:
    profile = db.query(EntityProfile).filter(EntityProfile.entity_id == entity_id).first()
    if not profile:
        profile = EntityProfile(
            entity_id=entity_id, entity_type=entity_type,
            known_dest_ports=[], known_protocols=[], known_peers=[],
            risk_score=0.0, reason_log=[], event_count=0,
        )
        db.add(profile)
    return profile


def _score_event_against_profile(profile: EntityProfile, event: NormalizedEvent) -> list:
    """Returns the list of (reason, contribution) pairs this event
    contributes -- computed against the profile's state *before* this event
    is folded in, so "new" genuinely means new relative to prior history."""
    if profile.event_count < MIN_BASELINE_EVENTS:
        return []  # still building the baseline -- nothing is "new" yet in a meaningful sense

    findings = []
    if event.dest_port is not None and event.dest_port not in (profile.known_dest_ports or []):
        findings.append(("new_dest_port", f"first time this entity has been seen touching port {event.dest_port}"))
    if event.network_protocol and event.network_protocol not in (profile.known_protocols or []):
        findings.append(("new_protocol", f"first time this entity has used protocol {event.network_protocol}"))
    if event.dest_ip and event.dest_ip not in (profile.known_peers or []):
        findings.append(("new_peer", f"first time this entity has communicated with {event.dest_ip}"))
    if (event.severity or "").lower() in ("high", "critical"):
        findings.append(("new_severity_high_or_above", f"a {event.severity} severity event from this entity"))
    return findings


def _apply_event_to_profile(profile: EntityProfile, event: NormalizedEvent) -> None:
    """Pure mutation of an already-resolved profile object -- no DB access,
    so it's safe to call in a tight loop over a batch regardless of the
    session's autoflush setting (see update_all_profiles's own cache, which
    exists specifically because relying on a query to detect an
    already-created-but-unflushed profile silently created duplicate rows
    for the same entity_id under autoflush=False -- caught by running this
    against real seeded data, not by the smaller synthetic unit tests)."""
    findings = _score_event_against_profile(profile, event)
    for reason_key, description in findings:
        contribution = _CONTRIBUTIONS[reason_key]
        profile.risk_score = min(MAX_SCORE, (profile.risk_score or 0) + contribution)
        profile.reason_log = (profile.reason_log or []) + [{
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "event_id": event.event_id,
            "reason": reason_key,
            "description": description,
            "contribution": contribution,
            "score_after": profile.risk_score,
        }]
        # Keep the reason log bounded -- an explainable trail, not an
        # unbounded audit table duplicated per profile.
        profile.reason_log = profile.reason_log[-200:]

    known_ports = set(profile.known_dest_ports or [])
    if event.dest_port is not None:
        known_ports.add(event.dest_port)
    profile.known_dest_ports = sorted(known_ports)[:500]

    known_protocols = set(profile.known_protocols or [])
    if event.network_protocol:
        known_protocols.add(event.network_protocol)
    profile.known_protocols = sorted(known_protocols)

    known_peers = set(profile.known_peers or [])
    if event.dest_ip:
        known_peers.add(event.dest_ip)
    profile.known_peers = sorted(known_peers)[:1000]

    profile.event_count = (profile.event_count or 0) + 1
    profile.last_event_at = event.timestamp
    profile.updated_at = datetime.now(timezone.utc)


def update_profile(db: Session, event: NormalizedEvent) -> EntityProfile:
    """Single-event convenience wrapper: resolves (or creates) the profile
    via a DB query, then applies the event. Fine for one-off/live calls; a
    batch loop should use update_all_profiles instead, which resolves
    profiles through an in-memory cache rather than a query per event."""
    entity_id = event.source_ip
    if not entity_id:
        return None
    profile = _get_or_create_profile(db, entity_id, "ip")
    _apply_event_to_profile(profile, event)
    return profile


def update_all_profiles(db: Session) -> dict:
    """Batch-builds/updates every entity's profile from NormalizedEvent rows
    not yet folded into a profile (sentinel_processed_at is null), processed
    in timestamp order per entity so "new relative to history" reflects real
    chronology. Safe to call repeatedly -- already-processed events are
    never re-scored. Cheap enough to run on demand for this project's real
    seeded data volume (tens of thousands of events); a live deployment
    would instead call update_profile() inline per ingested event or on a
    scheduler, same tradeoff as app/analytics/correlation.py's
    evaluate_all_rules."""
    events = (
        db.query(NormalizedEvent)
        .filter(NormalizedEvent.source_ip.isnot(None), NormalizedEvent.sentinel_processed_at.is_(None))
        .order_by(NormalizedEvent.source_ip.asc(), NormalizedEvent.timestamp.asc())
        .all()
    )

    # Resolve all profiles up front into an in-memory cache rather than one
    # query per event: under autoflush=False (used throughout this
    # project's own seed/reseed scripts for performance), a query-per-event
    # approach cannot see a same-entity profile created earlier in this same
    # batch until the session is flushed, so it would create -- and then try
    # to bulk-insert -- multiple EntityProfile rows for the same entity_id,
    # violating the primary key at commit time.
    #
    # Real bug found live (confirmed via Render's own oomKilled events
    # recurring hours after the correlation.py fix): this used to load EVERY
    # EntityProfile row, every 30s cycle, regardless of whether that entity
    # had any new events this cycle -- growing unbounded as more unique
    # source_ips accumulate in the real data (each profile also carries
    # known_peers/known_dest_ports/reason_log, so this isn't a cheap row).
    # `events` above is already the real bounded driving set (only
    # not-yet-processed rows); scoping the profile cache to just the
    # entities that actually appear in it keeps the same correctness
    # (same dedup-by-entity_id guarantee) while bounding memory to this
    # cycle's actual work instead of the whole profile table's history.
    needed_entity_ids = {e.source_ip for e in events}
    existing = (
        {p.entity_id: p for p in db.query(EntityProfile).filter(EntityProfile.entity_id.in_(needed_entity_ids)).all()}
        if needed_entity_ids else {}
    )

    updated = Counter()
    now = datetime.now(timezone.utc)
    for event in events:
        entity_id = event.source_ip
        profile = existing.get(entity_id)
        if not profile:
            profile = EntityProfile(
                entity_id=entity_id, entity_type="ip",
                known_dest_ports=[], known_protocols=[], known_peers=[],
                risk_score=0.0, reason_log=[], event_count=0,
            )
            db.add(profile)
            existing[entity_id] = profile
        _apply_event_to_profile(profile, event)
        event.sentinel_processed_at = now
        updated[entity_id] += 1
    db.commit()
    return {"entities_updated": len(updated), "events_processed": sum(updated.values())}
