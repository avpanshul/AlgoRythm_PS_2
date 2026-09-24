from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.models.all import NormalizedEvent

router = APIRouter()

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
        
        date_trunc_expr = func.date_trunc('hour', NormalizedEvent.timestamp)
        events_per_hour = db.query(
            date_trunc_expr.label("time_bucket"),
            func.count(NormalizedEvent.event_id).label("count")
        ).filter(NormalizedEvent.timestamp >= one_day_ago).group_by(date_trunc_expr).order_by(date_trunc_expr).all()
        
        events_over_time = [
            {"time": r.time_bucket.isoformat(), "count": r.count}
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
