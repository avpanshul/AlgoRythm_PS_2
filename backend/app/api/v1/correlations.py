"""Correlation API (ULPF-phase2-prompt.md E1) -- read the correlated
incidents the engine (app/analytics/correlation.py) has produced, and
trigger an evaluation pass on demand."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.all import CorrelatedIncident, NormalizedEvent, User
from app.analytics.correlation import evaluate_all_rules

router = APIRouter()


@router.post("/correlations/evaluate")
def trigger_evaluation(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Runs every correlation rule against currently-stored events. Cheap
    enough to call on demand for a small/medium event volume; a real
    deployment would schedule this (see app/workers/) rather than rely on
    someone calling it by hand."""
    summary = evaluate_all_rules(db)
    return {"new_incidents_by_rule": summary, "total_new": sum(summary.values())}


@router.get("/correlations")
def list_correlations(
    status: Optional[str] = None,
    rule_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(CorrelatedIncident)
    if status:
        q = q.filter(CorrelatedIncident.status == status)
    if rule_id:
        q = q.filter(CorrelatedIncident.rule_id == rule_id)
    total = q.count()
    items = q.order_by(CorrelatedIncident.last_event_at.desc()).offset((page - 1) * size).limit(size).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": i.id,
                "rule_id": i.rule_id,
                "rule_name": i.rule_name,
                "correlate_key": i.correlate_key,
                "distinct_source_count": i.distinct_source_count,
                "stage_summary": i.stage_summary,
                "event_count": len(i.event_ids or []),
                "first_event_at": i.first_event_at.isoformat() if i.first_event_at else None,
                "last_event_at": i.last_event_at.isoformat() if i.last_event_at else None,
                "status": i.status,
                "owner": i.owner,
            }
            for i in items
        ],
    }


@router.get("/correlations/{correlation_id}")
def get_correlation(correlation_id: str, db: Session = Depends(get_db)):
    incident = db.query(CorrelatedIncident).filter(CorrelatedIncident.id == correlation_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Correlation not found")
    events = (
        db.query(NormalizedEvent)
        .filter(NormalizedEvent.event_id.in_(incident.event_ids or []))
        .order_by(NormalizedEvent.timestamp.asc())
        .all()
    )
    return {
        "id": incident.id,
        "rule_id": incident.rule_id,
        "rule_name": incident.rule_name,
        "correlate_key": incident.correlate_key,
        "distinct_source_count": incident.distinct_source_count,
        "stage_summary": incident.stage_summary,
        "status": incident.status,
        "owner": incident.owner,
        "first_event_at": incident.first_event_at.isoformat() if incident.first_event_at else None,
        "last_event_at": incident.last_event_at.isoformat() if incident.last_event_at else None,
        "events": [e.canonical_json for e in events if e.canonical_json],
    }
