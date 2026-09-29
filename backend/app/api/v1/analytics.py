from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.core.db_utils import date_trunc_expr, bucket_label
from app.models.all import NormalizedEvent, Source

router = APIRouter()


@router.get("/analytics/quality-summary")
def get_quality_summary(db: Session = Depends(get_db)):
    """Real per-source quality scores + the epistemic classification
    (no-evidence / insufficient-data / evidence-of-absence / sufficient-evidence)
    stored on each event's canonical_json by the pipeline -- see
    app/analytics/epistemic.py and app/core/processing.py."""
    try:
        overall_avg = db.query(func.avg(NormalizedEvent.quality_score)).scalar()

        by_source_rows = db.query(
            NormalizedEvent.source_id,
            func.avg(NormalizedEvent.quality_score).label("avg_quality"),
            func.count(NormalizedEvent.event_id).label("event_count"),
        ).filter(NormalizedEvent.source_id.isnot(None)).group_by(NormalizedEvent.source_id).all()

        source_names = {s.id: s.name for s in db.query(Source).all()}

        # Aggregated in Python rather than with a DB-side JSON path expression
        # (e.g. Postgres's ->>'category') so this works identically across
        # database backends. Capped at the 10,000 most recent events -- an
        # approximate distribution, not an exact count over the full table.
        RECENT_LIMIT = 10000
        epistemic_dist: dict = {}
        recent = db.query(NormalizedEvent.canonical_json).order_by(
            NormalizedEvent.created_at.desc()
        ).limit(RECENT_LIMIT).all()
        for (canonical,) in recent:
            category = ((canonical or {}).get("quality") or {}).get("epistemic", {}).get("category")
            if category:
                epistemic_dist[category] = epistemic_dist.get(category, 0) + 1

        return {
            "overall_avg_quality": round(float(overall_avg), 1) if overall_avg is not None else None,
            "by_source": [
                {
                    "source_id": sid,
                    "source_name": source_names.get(sid, sid),
                    "avg_quality": round(float(q), 1) if q is not None else None,
                    "event_count": c,
                }
                for sid, q, c in by_source_rows
            ],
            "epistemic_distribution": epistemic_dist,
        }
    except Exception as e:
        return {"error": str(e), "overall_avg_quality": None, "by_source": [], "epistemic_distribution": {}}

@router.get("/risk")
def get_risk_summary(db: Session = Depends(get_db)):
    try:
        # Risk Distribution
        risk_levels = db.query(
            NormalizedEvent.risk_level, 
            func.count(NormalizedEvent.event_id).label('count')
        ).group_by(NormalizedEvent.risk_level).all()
        risk_dist = {r.risk_level: r.count for r in risk_levels if r.risk_level}

        # Average and Max Risk
        avg_risk = db.query(func.avg(NormalizedEvent.risk_score)).scalar() or 0
        max_risk = db.query(func.max(NormalizedEvent.risk_score)).scalar() or 0

        # Critical Events
        critical_events_query = db.query(NormalizedEvent).filter(NormalizedEvent.risk_score >= 80).order_by(NormalizedEvent.risk_score.desc()).limit(5).all()
        critical_events = [e.canonical_json for e in critical_events_query if e.canonical_json]

        return {
            "risk_distribution": risk_dist,
            "average_risk_score": float(avg_risk),
            "max_risk_score": max_risk,
            "critical_events_count": len(critical_events),
            "critical_events": critical_events
        }
    except Exception as e:
        return {"error": str(e), "risk_distribution": {}, "critical_events": []}

@router.get("/stats")
def get_system_stats(db: Session = Depends(get_db)):
    try:
        total_events = db.query(func.count(NormalizedEvent.event_id)).scalar() or 0

        # Formats
        formats_query = db.query(NormalizedEvent.parser_format, func.count(NormalizedEvent.event_id)).group_by(NormalizedEvent.parser_format).all()
        formats = {f: c for f, c in formats_query if f}

        # Severities
        severities_query = db.query(NormalizedEvent.severity, func.count(NormalizedEvent.event_id)).group_by(NormalizedEvent.severity).all()
        severities = {s: c for s, c in severities_query if s}

        # Actions
        actions_query = db.query(NormalizedEvent.action, func.count(NormalizedEvent.event_id)).group_by(NormalizedEvent.action).order_by(func.count(NormalizedEvent.event_id).desc()).limit(10).all()
        top_actions = {a: c for a, c in actions_query if a}

        # Events over time (last 24h)
        now = datetime.now(timezone.utc)
        one_day_ago = now - timedelta(hours=24)
        
        hour_bucket = date_trunc_expr(db, "hour", NormalizedEvent.timestamp)
        events_per_hour = db.query(
            hour_bucket.label("time_bucket"),
            func.count(NormalizedEvent.event_id).label("count")
        ).filter(NormalizedEvent.timestamp >= one_day_ago).group_by(hour_bucket).order_by(hour_bucket).all()

        events_over_time = [
            {"time": bucket_label(r.time_bucket), "count": r.count}
            for r in events_per_hour if r.time_bucket
        ]

        return {
            "total_events": total_events,
            "formats": formats,
            "severities": severities,
            "top_actions": top_actions,
            "events_over_time": events_over_time
        }
    except Exception as e:
        return {"error": str(e), "total_events": 0}
