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

    # Parse success/failure rate, all-time. Earlier versions of this scoped
    # the numerator/denominator to a rolling 24h cohort (joining DLQEvent to
    # the raw event's own received_at, to fix an even earlier bug where a
    # replay job's fresh DLQEvent rows for old raw events produced a
    # negative "-142.9% success rate"). That 24h scoping is itself gone now:
    # see the comment below for why.
    #
    # Real bug found live: preferring the 24h cohort here made "Parse
    # Success" read 100.0% (zero failures in the last 24h) directly next to
    # a "Failed / DLQ" widget showing the all-time count (4,415+) -- two
    # different time scopes shown as if they were the same metric, so a
    # healthy recent window looked like it was contradicting a large
    # historical backlog. Both widgets now describe the same all-time
    # population (total_normalized vs total_dlq), so the two numbers on the
    # dashboard actually reconcile with each other. Return null only when
    # there is literally nothing to rate, so the UI shows an honest empty
    # state instead of a fabricated 100%.
    def _success_pct(ok: int, failed: int):
        denom = ok + failed
        if denom <= 0:
            return None
        return max(0.0, min(100.0, round((ok / denom) * 100, 1)))

    success_rate = _success_pct(total_normalized, total_dlq)

    # Retry count
    retry_count = db.query(func.sum(DLQEvent.retry_count)).scalar() or 0

    # Average quality score
    avg_quality = db.query(func.avg(NormalizedEvent.quality_score)).scalar()
    avg_quality = round(avg_quality, 1) if avg_quality else 0

    # Real average processing latency: received_at (raw ingest) -> created_at
    # (normalized row written), over the last 24h -- was a hardcoded
    # "Simulated average" placeholder (45ms) that never reflected real
    # pipeline behavior; computed for real now, in Python (SQLite has no
    # portable EXTRACT(EPOCH FROM ...), and this only needs to run over a
    # bounded recent window, not the full table).
    recent_pairs = (
        db.query(RawEventMetadata.received_at, NormalizedEvent.created_at)
        .join(NormalizedEvent, NormalizedEvent.event_id == RawEventMetadata.event_id)
        .filter(RawEventMetadata.received_at >= one_day_ago)
        .limit(1000)
        .all()
    )
    latencies_ms = [
        (created - received).total_seconds() * 1000
        for received, created in recent_pairs
        if received is not None and created is not None and created >= received
    ]
    avg_latency_ms = round(sum(latencies_ms) / len(latencies_ms), 1) if latencies_ms else None

    parse_failure_rate = (
        round(100.0 - success_rate, 1) if success_rate is not None else None
    )
    parsing_status = (
        "healthy" if success_rate is not None and success_rate > 90
        else ("warning" if success_rate is not None else "healthy")
    )
    parsing_metric = f"{success_rate}%" if success_rate is not None else "n/a"

    return {
        "ingestion_rate": ingested_1h,
        "processing_rate": processed_1h,
        "queue_lag": max(0, total_raw - total_normalized - total_dlq),
        "parse_success_rate": success_rate,
        "parse_failure_rate": parse_failure_rate,
        "dlq_count": total_dlq,
        "retry_count": retry_count,
        "processing_latency_ms": avg_latency_ms,  # real, computed above; null if no recent pairs exist
        "storage_health": "healthy",
        "avg_quality_score": avg_quality,
        "total_raw_events": total_raw,
        "total_normalized_events": total_normalized,
        "last_updated": now.isoformat(),
        "stages": [
            {"name": "Sources", "status": "healthy", "metric": f"{total_raw}"},
            {"name": "Ingestion", "status": "healthy", "metric": f"{ingested_1h}/hr"},
            {"name": "Parsing", "status": parsing_status, "metric": parsing_metric},
            {"name": "Normalization", "status": "healthy", "metric": f"{total_normalized}"},
            {"name": "Redaction", "status": "healthy", "metric": "Active"},
            {"name": "Integrity", "status": "healthy", "metric": "SHA-256"},
            {"name": "Storage", "status": "healthy", "metric": "OK"},
        ],
    }
