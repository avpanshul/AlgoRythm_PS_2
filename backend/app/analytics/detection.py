"""Volume-based anomaly signals: silent sources, spikes/drops, and peer
deviation. Computed on demand (no scheduler in this deployment yet -- these are
called from API routes, or could be polled by a cron/worker later) by comparing
recent event counts against each source's own historical baseline and against
its peer group (same device_type). Every result carries the reason, the
threshold used, and the baseline sample size it was judged against, matching
the explainable-scoring approach used for per-event risk (see
app/core/processing.py:compute_risk_score).
"""
from datetime import datetime, timezone, timedelta
from statistics import mean, pstdev
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.all import NormalizedEvent, Source


def _as_naive_utc(dt):
    """SQLite silently drops tzinfo on DATETIME columns -- a value written as
    tz-aware UTC comes back naive on read (the same real bug found and
    fixed for the audit-log hash chain, Part D5). Comparing a naive value
    read back from the DB against a tz-aware `datetime.now(timezone.utc)`
    raises `TypeError: can't compare offset-naive and offset-aware
    datetimes` in Python -- found live by scripts/demo_flow.py's
    silent-source step, which this module had apparently never been
    exercised against non-empty real data by before. Normalizing every
    datetime used here to naive-UTC (never aware) makes both sides of every
    comparison consistent regardless of what a given DB backend does to
    tzinfo on round-trip -- correct on SQLite (which strips it) and on
    Postgres (which doesn't) alike, since both represent the same instant
    once reduced to naive UTC."""
    if dt is not None and dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _window_counts(db: Session, source_id: str, window_minutes: int, num_windows: int) -> list:
    """Event counts for `num_windows` consecutive windows of `window_minutes`
    ending now, oldest first."""
    now = _as_naive_utc(datetime.now(timezone.utc))
    counts = []
    for i in range(num_windows, 0, -1):
        end = now - timedelta(minutes=window_minutes * (i - 1))
        start = end - timedelta(minutes=window_minutes)
        c = db.query(func.count(NormalizedEvent.event_id)).filter(
            NormalizedEvent.source_id == source_id,
            NormalizedEvent.timestamp >= start,
            NormalizedEvent.timestamp < end,
        ).scalar() or 0
        counts.append(c)
    return counts


def detect_silent_sources(db: Session, silence_minutes: int = 60) -> list:
    """Sources with events somewhere in their history but none in the last
    `silence_minutes` -- distinct from a source that has simply never sent
    anything, which isn't "gone silent"."""
    now = _as_naive_utc(datetime.now(timezone.utc))
    cutoff = now - timedelta(minutes=silence_minutes)
    results = []
    for source in db.query(Source).filter(Source.enabled == True).all():
        last_seen = _as_naive_utc(db.query(func.max(NormalizedEvent.timestamp)).filter(
            NormalizedEvent.source_id == source.id
        ).scalar())
        if last_seen is None:
            continue
        if last_seen < cutoff:
            silent_for_min = int((now - last_seen).total_seconds() // 60)
            results.append({
                "source_id": source.id,
                "source_name": source.name,
                "last_seen": last_seen.isoformat(),
                "silent_for_minutes": silent_for_min,
                "threshold_minutes": silence_minutes,
                "reason": f"no events received in {silent_for_min} minutes (threshold {silence_minutes}m)",
            })
    return results


def detect_volume_anomalies(db: Session, window_minutes: int = 60, baseline_windows: int = 24, z_threshold: float = 2.5) -> list:
    """Per-source spike/drop detection: current window vs. a rolling baseline of
    `baseline_windows` prior windows of the same length, flagged when the
    z-score of the current count against that baseline exceeds `z_threshold`."""
    results = []
    for source in db.query(Source).filter(Source.enabled == True).all():
        counts = _window_counts(db, source.id, window_minutes, baseline_windows + 1)
        baseline, current = counts[:-1], counts[-1]
        if len(baseline) < 3 or all(c == 0 for c in baseline):
            continue  # not enough history to judge this source yet
        avg = mean(baseline)
        sd = pstdev(baseline) or 1.0
        z = (current - avg) / sd
        if abs(z) >= z_threshold:
            results.append({
                "source_id": source.id,
                "source_name": source.name,
                "direction": "spike" if z > 0 else "drop",
                "current_count": current,
                "baseline_mean": round(avg, 2),
                "baseline_stddev": round(sd, 2),
                "baseline_size": len(baseline),
                "z_score": round(z, 2),
                "threshold_z": z_threshold,
                "reason": f"{current} events in the last {window_minutes}m vs. baseline mean {round(avg, 1)} over {len(baseline)} prior windows (z={round(z, 2)}, threshold {z_threshold})",
            })
    return results


def detect_peer_deviation(db: Session, window_minutes: int = 60, z_threshold: float = 2.0) -> list:
    """Compares each source's current-window event count to the mean of its
    peer group (same device_type), flagging outliers within that group."""
    results = []
    groups: dict = {}
    for source in db.query(Source).filter(Source.enabled == True).all():
        groups.setdefault(source.device_type or "unknown", []).append(source)

    now = _as_naive_utc(datetime.now(timezone.utc))
    start = now - timedelta(minutes=window_minutes)

    for device_type, group in groups.items():
        if len(group) < 3:
            continue  # need a real peer group for "deviation from peers" to mean anything
        counts = {
            source.id: db.query(func.count(NormalizedEvent.event_id)).filter(
                NormalizedEvent.source_id == source.id, NormalizedEvent.timestamp >= start
            ).scalar() or 0
            for source in group
        }
        values = list(counts.values())
        avg = mean(values)
        sd = pstdev(values) or 1.0
        for source in group:
            z = (counts[source.id] - avg) / sd
            if abs(z) >= z_threshold:
                results.append({
                    "source_id": source.id,
                    "source_name": source.name,
                    "peer_group": device_type,
                    "peer_group_size": len(group),
                    "current_count": counts[source.id],
                    "peer_mean": round(avg, 2),
                    "z_score": round(z, 2),
                    "threshold_z": z_threshold,
                    "reason": f"{counts[source.id]} events vs. peer group '{device_type}' mean {round(avg, 1)} across {len(group)} sources (z={round(z, 2)}, threshold {z_threshold})",
                })
    return results
