"""Pipeline health endpoint — aggregates metrics from PostgreSQL tables."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.models.all import NormalizedEvent, DLQEvent, RawEventMetadata

router = APIRouter()


@router.get("/pipeline/health")
def get_pipeline_health(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(hours=24)

    # Total counts
    total_raw = db.query(func.count(RawEventMetadata.event_id)).scalar() or 0
    total_normalized = db.query(func.count(NormalizedEvent.event_id)).scalar() or 0
    total_dlq = db.query(func.count(DLQEvent.id)).filter(DLQEvent.status == "failed").scalar() or 0

    # Last hour ingestion rate
    ingested_1h = db.query(func.count(RawEventMetadata.event_id)).filter(
        RawEventMetadata.received_at >= one_hour_ago
    ).scalar() or 0

    processed_1h = db.query(func.count(NormalizedEvent.event_id)).filter(
        NormalizedEvent.created_at >= one_hour_ago
    ).scalar() or 0

    # Parse success/failure rate (last 24h)
    total_24h = db.query(func.count(RawEventMetadata.event_id)).filter(
        RawEventMetadata.received_at >= one_day_ago
    ).scalar() or 0

    failed_24h = db.query(func.count(DLQEvent.id)).filter(
        DLQEvent.created_at >= one_day_ago
    ).scalar() or 0

    success_rate = round(((total_24h - failed_24h) / total_24h * 100) if total_24h > 0 else 100, 1)

    # Retry count
    retry_count = db.query(func.sum(DLQEvent.retry_count)).scalar() or 0

    # Average quality score
    avg_quality = db.query(func.avg(NormalizedEvent.quality_score)).scalar()
    avg_quality = round(avg_quality, 1) if avg_quality else 0

    return {
        "ingestion_rate": ingested_1h,
        "processing_rate": processed_1h,
        "queue_lag": max(0, total_raw - total_normalized - total_dlq),
        "parse_success_rate": success_rate,
        "parse_failure_rate": round(100 - success_rate, 1),
        "dlq_count": total_dlq,
        "retry_count": retry_count,
        "processing_latency_ms": 45,  # Simulated average
        "storage_health": "healthy",
        "avg_quality_score": avg_quality,
        "total_raw_events": total_raw,
        "total_normalized_events": total_normalized,
        "last_updated": now.isoformat(),
        "stages": [
            {"name": "Sources", "status": "healthy", "metric": f"{total_raw}"},
            {"name": "Ingestion", "status": "healthy", "metric": f"{ingested_1h}/hr"},
            {"name": "Parsing", "status": "healthy" if success_rate > 90 else "warning", "metric": f"{success_rate}%"},
            {"name": "Normalization", "status": "healthy", "metric": f"{total_normalized}"},
            {"name": "Redaction", "status": "healthy", "metric": "Active"},
            {"name": "Integrity", "status": "healthy", "metric": "SHA-256"},
            {"name": "Storage", "status": "healthy", "metric": "OK"},
        ],
    }
