r"""Item 2: spark detection.

Closes a real, verified gap (live audit, 2026-09-28): `reconstruct_attack_path`
(app/analytics/graph.py) existed and worked correctly, but nothing in the
codebase ever decided *which* entity to trace, or explained why -- an
analyst had to already know/guess a starting IP and type it into the UI.

Two explicit, explainable trigger rules -- never a black-box score, always
recorded as a real `reason` string on the Spark row:

  1. "correlated_incident" -- the earliest event's entity (source_ip,
     falling back to user_name) in a newly-opened CorrelatedIncident. This
     is the correlation engine's own real "an attack pattern actually
     matched" signal, just not previously wired to anything downstream.
  2. "risk_threshold" -- an EntityProfile (app/ai/sentinel.py) whose
     risk_score crosses SPARK_RISK_THRESHOLD for the first time. Dedup'd
     per entity (one spark per entity for this trigger, ever) so a score
     hovering near the threshold doesn't spam a new spark every cycle.

Advisory only, matching this project's existing E8 ground rule (see
app/analytics/graph.py's own docstring): a spark says "here's a real,
explainable starting point and the real path reconstructed from it," never
a prediction of what happens next.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.all import CorrelatedIncident, EntityProfile, NormalizedEvent, Spark
from app.analytics.graph import reconstruct_attack_path

log = logging.getLogger("spark_detection")


def _entity_for_incident(db: Session, incident: CorrelatedIncident) -> str | None:
    """The real entity behind this incident's earliest matched event --
    source_ip preferred (what reconstruct_attack_path traces), user_name as
    a fallback for incidents whose events don't carry an IP."""
    events = (
        db.query(NormalizedEvent)
        .filter(NormalizedEvent.event_id.in_(incident.event_ids))
        .order_by(NormalizedEvent.timestamp.asc())
        .limit(1)
        .all()
    )
    if not events:
        return None
    first = events[0]
    return first.source_ip or first.user_name


def _record_spark(db: Session, entity: str, trigger_type: str, reason: str,
                   source_incident_id: str = None, risk_score: float = None) -> Spark:
    result = reconstruct_attack_path(db, entity)
    spark = Spark(
        id=f"spark-{uuid.uuid4().hex[:16]}",
        entity=entity,
        trigger_type=trigger_type,
        reason=reason,
        source_incident_id=source_incident_id,
        risk_score=risk_score,
        path=result.get("path", []),
        hop_count=len(result.get("path", [])),
        front=result.get("front"),
        proximity_watchlist=result.get("proximity_watchlist", []),
    )
    db.add(spark)
    return spark


def detect_sparks_from_new_incidents(db: Session, incident_ids: list) -> list:
    """Call with the real CorrelatedIncident ids opened THIS cycle (e.g.
    live_detection.py's run_detection_cycle already returns cases_opened's
    correlation_id). One spark per incident, never a duplicate for the same
    incident (checked by source_incident_id)."""
    sparks = []
    for incident_id in incident_ids:
        if db.query(Spark).filter(Spark.source_incident_id == incident_id).first():
            continue
        incident = db.query(CorrelatedIncident).filter(CorrelatedIncident.id == incident_id).first()
        if not incident:
            continue
        entity = _entity_for_incident(db, incident)
        if not entity:
            continue
        reason = (
            f"First event (at {incident.first_event_at.isoformat() if incident.first_event_at else 'unknown'}) "
            f"of newly-opened correlated incident '{incident.rule_name}' (rule={incident.rule_id}, "
            f"correlate_key={incident.correlate_key}) involves entity {entity}."
        )
        sparks.append(_record_spark(db, entity, "correlated_incident", reason, source_incident_id=incident_id))
    return sparks


def detect_sparks_from_risk_threshold(db: Session) -> list:
    """Any EntityProfile at/above SPARK_RISK_THRESHOLD that doesn't already
    have a risk_threshold-triggered spark. One-time per entity for this
    trigger (not re-fired every cycle just because the score stays high).

    Capped at SPARK_MAX_NEW_PER_CYCLE, highest-risk-first -- each spark does
    a real O(n) forward-time scan (reconstruct_attack_path), and a real
    dataset can have far more qualifying entities than it's safe to scan in
    one 30s cycle (this project's own demo DB has 132 at the default
    threshold). Entities not reached this cycle are picked up on a later
    one via the same query, never silently dropped."""
    threshold = settings.SPARK_RISK_THRESHOLD
    already_sparked = {
        row.entity for row in db.query(Spark.entity).filter(Spark.trigger_type == "risk_threshold").all()
    }
    candidates = (
        db.query(EntityProfile)
        .filter(EntityProfile.risk_score >= threshold)
        .order_by(EntityProfile.risk_score.desc())
        .all()
    )
    sparks = []
    for profile in candidates:
        if len(sparks) >= settings.SPARK_MAX_NEW_PER_CYCLE:
            break
        if profile.entity_id in already_sparked:
            continue
        reason = (
            f"Entity {profile.entity_id}'s behavioral risk_score ({profile.risk_score:.1f}) crossed the "
            f"configured SPARK_RISK_THRESHOLD ({threshold}) -- see app/ai/sentinel.py's reason_log on this "
            f"entity's profile for the real anomalies that built up this score."
        )
        sparks.append(_record_spark(db, profile.entity_id, "risk_threshold", reason, risk_score=profile.risk_score))
    return sparks


def run_spark_detection(db: Session, new_incident_ids: list = None) -> dict:
    """Entry point for the correlation cycle (app/services/live_detection.py).
    Must never raise out to the caller -- the 30s cycle it's hooked into
    cannot be broken by a spark-detection failure (caller also wraps this in
    try/except as defense in depth, but this function is honest about its
    own failure mode too rather than assuming the caller always will be)."""
    if not settings.ENABLE_SPARK_DETECTION:
        return {"enabled": False, "sparks_created": 0}
    try:
        from_incidents = detect_sparks_from_new_incidents(db, new_incident_ids or [])
        from_risk = detect_sparks_from_risk_threshold(db)
        db.commit()
        return {
            "enabled": True,
            "sparks_created": len(from_incidents) + len(from_risk),
            "from_correlated_incidents": len(from_incidents),
            "from_risk_threshold": len(from_risk),
        }
    except Exception as e:  # noqa: BLE001 -- must never break the caller's cycle
        db.rollback()
        log.exception("spark detection failed (will retry next cycle): %s", e)
        return {"enabled": True, "sparks_created": 0, "error": str(e)}
