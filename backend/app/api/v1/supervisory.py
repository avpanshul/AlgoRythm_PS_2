"""Multi-CSE supervisory view: an aggregate-only rollup across organizations
(Critical Sector Entities). A supervisor sees counts and rates per organization,
never another org's raw per-event detail -- that's the isolation boundary a
multi-tenant supervisory role needs. Full per-entity RBAC scoping (a supervisor
role that can *only* call this aggregate endpoint, never the raw /events one)
is a separate access-control change, tracked with the rest of RBAC.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.models.all import Organization, Source, NormalizedEvent
from app.analytics.detection import detect_silent_sources

router = APIRouter()


@router.get("/supervisory/organizations")
def supervisory_overview(window_hours: Optional[int] = Query(None, ge=1), db: Session = Depends(get_db)):
    """window_hours omitted (the default) means all-time, not a rolling
    24h/7d/30d window. Real bug found live: this pipeline's seeded/demo
    corpora are ingested once in a short real burst, not continuously --
    for that shape of data, a wall-clock-relative window is either always
    empty (nothing in the last 24h once a day has passed since seeding) or
    identical across 7d/30d (nothing exists in between), so it never
    actually differentiated anything here. A supervisor's real question is
    "what does this org's traffic look like overall", not "in the last N
    wall-clock hours" -- so all-time is now the real default; window_hours
    still works if a caller explicitly wants a bounded window."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=window_hours) if window_hours else None

    silent_source_ids = {s["source_id"] for s in detect_silent_sources(db)}

    overview = []
    for org in db.query(Organization).all():
        source_ids = [row[0] for row in db.query(Source.id).filter(Source.organization_id == org.id).all()]

        entry = {
            "organization_id": org.id,
            "organization_name": org.name,
            "sector": org.sector,
            "source_count": len(source_ids),
            "event_count": 0,
            "avg_quality": None,
            "avg_risk": None,
            "critical_events": 0,
            "silent_sources": len([sid for sid in source_ids if sid in silent_source_ids]),
        }

        if source_ids:
            base = db.query(NormalizedEvent).filter(NormalizedEvent.source_id.in_(source_ids))
            quality_q = db.query(func.avg(NormalizedEvent.quality_score)).filter(NormalizedEvent.source_id.in_(source_ids))
            risk_q = db.query(func.avg(NormalizedEvent.risk_score)).filter(NormalizedEvent.source_id.in_(source_ids))
            if start:
                base = base.filter(NormalizedEvent.timestamp >= start)
                quality_q = quality_q.filter(NormalizedEvent.timestamp >= start)
                risk_q = risk_q.filter(NormalizedEvent.timestamp >= start)

            entry["event_count"] = base.count()
            avg_quality = quality_q.scalar()
            avg_risk = risk_q.scalar()
            entry["avg_quality"] = round(avg_quality, 1) if avg_quality is not None else None
            entry["avg_risk"] = round(avg_risk, 1) if avg_risk is not None else None
            entry["critical_events"] = base.filter(NormalizedEvent.risk_level == "CRITICAL").count()

        overview.append(entry)

    return {"window_hours": window_hours, "organizations": overview}
