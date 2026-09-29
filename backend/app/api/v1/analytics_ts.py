"""Analytics Timeseries API."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.database import get_db
from app.core.db_utils import date_trunc_expr, bucket_label
from app.models.all import NormalizedEvent, DLQEvent
from app.analytics.detection import detect_silent_sources, detect_volume_anomalies, detect_peer_deviation

router = APIRouter()


@router.get("/analytics/silent-sources")
def get_silent_sources(silence_minutes: int = Query(60, ge=1), db: Session = Depends(get_db)):
    return {"silence_threshold_minutes": silence_minutes, "sources": detect_silent_sources(db, silence_minutes)}


@router.get("/analytics/volume-anomalies")
def get_volume_anomalies(
    window_minutes: int = Query(60, ge=1),
    baseline_windows: int = Query(24, ge=3),
    z_threshold: float = Query(2.5, gt=0),
    db: Session = Depends(get_db),
):
    return {
        "window_minutes": window_minutes,
        "baseline_windows": baseline_windows,
        "z_threshold": z_threshold,
        "anomalies": detect_volume_anomalies(db, window_minutes, baseline_windows, z_threshold),
    }


@router.get("/analytics/peer-deviation")
def get_peer_deviation(
    window_minutes: int = Query(60, ge=1),
    z_threshold: float = Query(2.0, gt=0),
    db: Session = Depends(get_db),
):
    return {
        "window_minutes": window_minutes,
        "z_threshold": z_threshold,
        "deviations": detect_peer_deviation(db, window_minutes, z_threshold),
    }


def _bucket_step(interval: str) -> timedelta:
    if interval == "minute":
        return timedelta(minutes=1)
    if interval == "day":
        return timedelta(days=1)
    return timedelta(hours=1)


def _floor_bucket(dt: datetime, interval: str) -> datetime:
    """Align a datetime to the start of its minute/hour/day bucket (UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    if interval == "minute":
        return dt.replace(second=0, microsecond=0)
    if interval == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(minute=0, second=0, microsecond=0)


def _fill_empty_buckets(merged: dict, start_date: datetime, end_date: datetime, interval: str) -> list:
    """Ensure every bucket in [start, end] exists so 1H/6H charts aren't
    blank just because only a subset of minutes/hours had traffic."""
    step = _bucket_step(interval)
    cursor = _floor_bucket(start_date, interval)
    end_floor = _floor_bucket(end_date, interval)
    # Cap fill size so a multi-year range can't explode (dashboard only
    # asks for <= 24h / 1-day buckets).
    max_buckets = 24 * 60 if interval == "minute" else (24 * 14 if interval == "hour" else 400)
    filled = []
    n = 0
    while cursor <= end_floor and n < max_buckets:
        # Match SQLite strftime labels (no tz suffix) and Postgres isoformat.
        candidates = [
            cursor.strftime("%Y-%m-%dT%H:%M:00") if interval == "minute"
            else (cursor.strftime("%Y-%m-%dT%H:00:00") if interval == "hour"
                  else cursor.strftime("%Y-%m-%dT00:00:00")),
            cursor.isoformat(),
            cursor.replace(tzinfo=None).isoformat(),
        ]
        row = None
        for c in candidates:
            if c in merged:
                row = merged[c]
                break
        if row is None:
            # Also try matching any merged key that starts with the naive stamp
            naive = candidates[0]
            for k, v in merged.items():
                if k.startswith(naive):
                    row = v
                    break
        if row is None:
            row = {
                "time": candidates[0],
                "events_normalized": 0,
                "avg_quality": 0.0,
                "parse_failures": 0,
            }
        filled.append(row)
        cursor += step
        n += 1
    return filled


@router.get("/analytics/timeseries")
def get_timeseries(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    interval: str = Query("hour", pattern="^(hour|day|minute)$"),
    source_id: Optional[str] = None,
    time_field: str = Query(
        "created_at",
        pattern="^(created_at|timestamp)$",
        description=(
            "created_at = when ULPF ingested/normalized the event (correct for "
            "Ingestion Trend). timestamp = the log's own event time (often "
            "historical for seeded corpora, so wall-clock 1H/6H windows look empty)."
        ),
    ),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    if not end_date:
        end_date = now
    if not start_date:
        start_date = end_date - timedelta(days=1)

    # Normalize to UTC, then drop tzinfo for SQLite (it stores naive UTC and
    # comparing aware vs naive silently returns zero rows -- the same class
    # of bug that emptied 1H/6H ingestion charts against a real seed).
    def _as_utc_naive(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt
        return dt.astimezone(timezone.utc).replace(tzinfo=None)

    start_date = _as_utc_naive(start_date)
    end_date = _as_utc_naive(end_date)
    # Keep timezone-aware copies only for response metadata / bucket filling.
    start_aware = start_date.replace(tzinfo=timezone.utc)
    end_aware = end_date.replace(tzinfo=timezone.utc)

    if time_field == "created_at":
        time_col = NormalizedEvent.created_at
    elif time_field == "timestamp":
        time_col = NormalizedEvent.timestamp
    else:
        raise HTTPException(status_code=400, detail="time_field must be created_at or timestamp")

    date_trunc_expr_norm = date_trunc_expr(db, interval, time_col)

    # Base query for normalized events
    q_norm = db.query(
        date_trunc_expr_norm.label("time_bucket"),
        func.count(NormalizedEvent.event_id).label("events_normalized"),
        func.avg(NormalizedEvent.quality_score).label("avg_quality"),
    ).filter(
        time_col >= start_date,
        time_col <= end_date,
    )

    if source_id:
        q_norm = q_norm.filter(NormalizedEvent.source_id == source_id)

    results_norm = q_norm.group_by(date_trunc_expr_norm).order_by(date_trunc_expr_norm).all()

    # Base query for failures (always by when the failure was recorded)
    date_trunc_dlq = date_trunc_expr(db, interval, DLQEvent.created_at)
    q_dlq = db.query(
        date_trunc_dlq.label("time_bucket"),
        func.count(DLQEvent.id).label("parse_failures"),
    ).filter(
        DLQEvent.created_at >= start_date,
        DLQEvent.created_at <= end_date,
    )

    if source_id:
        q_dlq = q_dlq.filter(DLQEvent.source_id == source_id)

    results_dlq = q_dlq.group_by(date_trunc_dlq).all()

    # Merge results
    merged = {}
    for r in results_norm:
        t = bucket_label(r.time_bucket)
        if t:
            merged[t] = {
                "time": t,
                "events_normalized": r.events_normalized or 0,
                "avg_quality": float(r.avg_quality) if r.avg_quality else 0.0,
                "parse_failures": 0,
            }

    for r in results_dlq:
        t = bucket_label(r.time_bucket)
        if t:
            if t not in merged:
                merged[t] = {
                    "time": t,
                    "events_normalized": 0,
                    "avg_quality": 0.0,
                    "parse_failures": 0,
                }
            merged[t]["parse_failures"] = r.parse_failures or 0

    # Fill empty buckets so 1H/6H still render a continuous axis (zeros where
    # nothing was ingested), instead of an empty chart that looks "broken".
    timeseries_data = _fill_empty_buckets(merged, start_aware, end_aware, interval)
    if not timeseries_data:
        timeseries_data = sorted(list(merged.values()), key=lambda x: x["time"])

    # Summary of failures by reason
    failure_reasons = db.query(
        DLQEvent.failure_reason,
        func.count(DLQEvent.id).label("count"),
    ).filter(
        DLQEvent.created_at >= start_date,
        DLQEvent.created_at <= end_date,
    ).group_by(DLQEvent.failure_reason).all()

    return {
        "start_date": start_aware.isoformat(),
        "end_date": end_aware.isoformat(),
        "interval": interval,
        "time_field": time_field,
        "timeseries": timeseries_data,
        "failures_by_reason": [
            {"name": r.failure_reason, "count": r.count}
            for r in failure_reasons
        ],
    }
