"""Analytics Timeseries API."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.database import get_db
from app.models.all import NormalizedEvent, DLQEvent

router = APIRouter()

@router.get("/analytics/timeseries")
def get_timeseries(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    interval: str = Query("hour", pattern="^(hour|day|minute)$"),
    source_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    if not end_date:
        end_date = now
    if not start_date:
        start_date = end_date - timedelta(days=1)
        
    date_trunc_expr = func.date_trunc(interval, NormalizedEvent.timestamp)
    
    # Base query for normalized events
    q_norm = db.query(
        date_trunc_expr.label("time_bucket"),
        func.count(NormalizedEvent.event_id).label("events_normalized"),
        func.avg(NormalizedEvent.quality_score).label("avg_quality"),
    ).filter(
        NormalizedEvent.timestamp >= start_date,
        NormalizedEvent.timestamp <= end_date
    )
    
    if source_id:
        q_norm = q_norm.filter(NormalizedEvent.source_id == source_id)
        
    results_norm = q_norm.group_by(date_trunc_expr).order_by(date_trunc_expr).all()
    
    # Base query for failures
    date_trunc_dlq = func.date_trunc(interval, DLQEvent.created_at)
    q_dlq = db.query(
        date_trunc_dlq.label("time_bucket"),
        func.count(DLQEvent.id).label("parse_failures"),
    ).filter(
        DLQEvent.created_at >= start_date,
        DLQEvent.created_at <= end_date
    )
    
    if source_id:
        q_dlq = q_dlq.filter(DLQEvent.source_id == source_id)
        
    results_dlq = q_dlq.group_by(date_trunc_dlq).all()
    
    # Merge results
    merged = {}
    for r in results_norm:
        t = r.time_bucket.isoformat() if r.time_bucket else None
        if t:
            merged[t] = {
                "time": t,
                "events_normalized": r.events_normalized or 0,
                "avg_quality": float(r.avg_quality) if r.avg_quality else 0.0,
                "parse_failures": 0
            }
            
    for r in results_dlq:
        t = r.time_bucket.isoformat() if r.time_bucket else None
        if t:
            if t not in merged:
                merged[t] = {
                    "time": t,
                    "events_normalized": 0,
                    "avg_quality": 0.0,
                    "parse_failures": 0
                }
            merged[t]["parse_failures"] = r.parse_failures or 0

    timeseries_data = sorted(list(merged.values()), key=lambda x: x["time"])
    
    # Summary of failures by reason
    failure_reasons = db.query(
        DLQEvent.failure_reason,
        func.count(DLQEvent.id).label("count")
    ).filter(
        DLQEvent.created_at >= start_date,
        DLQEvent.created_at <= end_date
    ).group_by(DLQEvent.failure_reason).all()

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "interval": interval,
        "timeseries": timeseries_data,
        "failures_by_reason": [
            {"name": r.failure_reason, "count": r.count}
            for r in failure_reasons
        ]
    }
