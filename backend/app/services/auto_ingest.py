r"""Twice-daily automatic real-data re-ingestion.

Feeds datasets/real/cloudtrail_corpus.jsonl (real AWS CloudTrail records from
a Stratus Red Team attack simulation against a real AWS account --
invictus-ir/aws_dataset, MIT license; see build_cloudtrail_corpus.py's
provenance docstring) through the actual production pipeline
(app.core.processing.process_raw_event), the same call seed.py's
seed_real_events() and app/api/v1/ingestion.py's live ingestion path both
use. No log line here is generated, templated, or synthesized -- every row
was downloaded verbatim as part of that dataset. Picked over the loghub/EVTX/
Zeek corpora already seeded at install time because CloudTrail is the one
still large enough (2,900 real records) relative to what's already been
ingested that a real recurring "new real data" cadence makes sense here
rather than degrading into "same rows, again" on day one.

Why this exists rather than just re-running seed.py's seed_real_events() on a
timer: seed_real_events() has no dedup and no run bookkeeping -- run it twice
and every already-ingested line gets a second, byte-identical NormalizedEvent
row. This module (a) skips any raw line whose sha256 is already in
RawEventMetadata (same check top-up/backfill work earlier in this project
used), (b) caps a single run to AUTO_INGEST_BATCH_SIZE new rows so the
scheduler thread doesn't block on walking the whole remaining corpus at once,
and (c) once every real row in the corpus has been ingested, honestly reports
corpus_exhausted=True and ingests nothing further -- it does not wrap around
and re-ingest, and it does not fabricate new rows to keep the "twice daily"
cadence looking busy.

Deployment fit: deploy/k8s/06-backend.yaml pins the backend Deployment to
replicas: 1 specifically because of the Merkle tree's single-writer
assumption (see docs/benchmarks.md) -- the same constraint that already rules
out running >1 copy of app/services/live_detection.py's background thread.
That makes the simple in-process daemon-thread pattern (matching
live_detection.py) the right fit here too: no second scheduling process, no
distributed lock service, no new infrastructure. Duplicate-run prevention
(see IngestionRun's docstring in app/models/all.py) is still real and
DB-enforced, not merely "there's only one replica so it's probably fine" --
so it stays correct even if that replica count assumption ever changes, and
it's what makes `python -m app.services.auto_ingest --once` safe to also run
by hand without double-processing a slot the background thread already
covered.
"""
import argparse
import hashlib
import json
import logging
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.local_storage import save_raw_log
from app.core.processing import process_raw_event
from app.models.all import IngestionRun, RawEventMetadata

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] auto_ingest: %(message)s")
log = logging.getLogger("auto_ingest")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS_PATH = os.path.join(BACKEND_DIR, "datasets", "real", "cloudtrail_corpus.jsonl")
CORPUS_SOURCE_ID = "AWS-CLOUDTRAIL"
INGESTION_PROTOCOL = "auto-ingest-cloudtrail"

_stop_event = threading.Event()
_thread = None


def _load_corpus_rows() -> list:
    if not os.path.exists(CORPUS_PATH):
        log.warning("corpus not found at %s -- nothing to auto-ingest", CORPUS_PATH)
        return []
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _ingest_row(db: Session, raw_log: str, source_id: str):
    """Same real-pipeline call pattern as seed.py's seed_real_events(): hash,
    write to the raw vault, insert RawEventMetadata, then hand off to the
    actual normalization/scoring/Merkle-append pipeline."""
    event_id = f"evt_{uuid.uuid4().hex}"
    raw_sha256 = hashlib.sha256(raw_log.encode("utf-8")).hexdigest()
    received_at = datetime.now(timezone.utc)
    raw_location = f"{received_at.strftime('%Y/%m/%d')}/{event_id}.txt"

    save_raw_log(raw_location, raw_log)
    db.add(RawEventMetadata(
        event_id=event_id, source_id=source_id, received_at=received_at,
        ingestion_protocol=INGESTION_PROTOCOL, raw_sha256=raw_sha256,
        raw_location=raw_location, processing_status="processing",
    ))
    db.commit()

    norm_event = process_raw_event(db, event_id, raw_log, source_id, raw_sha256, raw_location)
    return norm_event


def run_once(db: Session, trigger: str = "manual", run_key: str = None) -> dict:
    """Runs one ingestion pass and records it as an IngestionRun row. Returns
    a dict describing what actually happened -- never claims events were
    ingested that weren't. `run_key` is the deterministic PK for a scheduled
    slot (see IngestionRun's docstring); if that row already exists, this
    returns immediately without touching the pipeline at all (the actual
    duplicate-run guard, not just a courtesy check -- the INSERT below is
    what a second, racing caller would collide on)."""
    run_id = run_key or f"manual-{uuid.uuid4().hex[:12]}"
    run = IngestionRun(id=run_id, trigger=trigger, status="running")
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        log.info("run %s already exists -- skipping (duplicate-run guard)", run_id)
        return {"run_id": run_id, "skipped_as_duplicate_run": True}

    try:
        rows = _load_corpus_rows()
        existing_hashes = {
            h for (h,) in db.query(RawEventMetadata.raw_sha256).all()
        }

        new_rows = [r for r in rows if hashlib.sha256(r["raw"].encode("utf-8")).hexdigest() not in existing_hashes]
        skipped = len(rows) - len(new_rows)
        batch = new_rows[: settings.AUTO_INGEST_BATCH_SIZE]

        ok_count = 0
        dlq_count = 0
        format_counts: dict = {}
        seen_this_run = set()
        for row in batch:
            raw_log = row["raw"]
            sha = hashlib.sha256(raw_log.encode("utf-8")).hexdigest()
            if sha in seen_this_run:
                # the corpus file itself can contain an exact duplicate line;
                # don't double-ingest within the same run either.
                skipped += 1
                continue
            seen_this_run.add(sha)
            source_id = row.get("source_id") or CORPUS_SOURCE_ID
            norm_event = _ingest_row(db, raw_log, source_id)
            if norm_event is not None:
                ok_count += 1
                fmt = norm_event.parser_format
                format_counts[fmt] = format_counts.get(fmt, 0) + 1
            else:
                dlq_count += 1

        corpus_exhausted = len(new_rows) <= len(batch)

        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.new_events_ingested = ok_count
        run.skipped_duplicates = skipped
        run.dlq_count = dlq_count
        run.format_breakdown = format_counts
        run.corpus_exhausted = corpus_exhausted
        db.commit()

        log.info(
            "run %s (%s): %d new events, %d skipped duplicates, %d to DLQ, corpus_exhausted=%s",
            run_id, trigger, ok_count, skipped, dlq_count, corpus_exhausted,
        )
        return {
            "run_id": run_id, "new_events_ingested": ok_count, "skipped_duplicates": skipped,
            "dlq_count": dlq_count, "formats": format_counts, "corpus_exhausted": corpus_exhausted,
        }
    except Exception as e:  # noqa: BLE001 -- a failed run must be recorded, not silently lost
        db.rollback()
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = str(e)
        db.commit()
        log.exception("run %s failed", run_id)
        return {"run_id": run_id, "error": str(e)}


def _parse_times(times_str: str) -> list:
    slots = []
    for part in times_str.split(","):
        part = part.strip()
        if not part:
            continue
        hh, mm = part.split(":")
        slots.append((int(hh), int(mm)))
    return slots


def _run_key_for(dt: datetime, hh: int, mm: int) -> str:
    return f"{dt.strftime('%Y-%m-%d')}-{hh:02d}:{mm:02d}"


def _catch_up_missed_slots_today(db: Session, slots: list):
    """On startup, any configured slot earlier today that has no
    IngestionRun row yet is run immediately, once, as trigger="startup_catchup"
    -- covers the real case of the process being down at 08:00 and coming up
    at 09:00. Never backfills a *previous* day's slot; that's a genuinely
    missed run, not something to silently paper over by pretending it
    happened."""
    now = datetime.now()
    for hh, mm in slots:
        slot_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if slot_dt > now:
            continue
        run_key = _run_key_for(now, hh, mm)
        if db.query(IngestionRun).filter(IngestionRun.id == run_key).first():
            continue
        log.info("catching up missed slot %s on startup", run_key)
        run_once(db, trigger="startup_catchup", run_key=run_key)


def _loop(slots: list):
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        _catch_up_missed_slots_today(db, slots)
    finally:
        db.close()

    last_checked_minute = None
    while not _stop_event.is_set():
        try:
            now = datetime.now()
            minute_key = now.strftime("%Y-%m-%d %H:%M")
            if minute_key != last_checked_minute:
                last_checked_minute = minute_key
                for hh, mm in slots:
                    if now.hour == hh and now.minute == mm:
                        run_key = _run_key_for(now, hh, mm)
                        db = SessionLocal()
                        try:
                            run_once(db, trigger="scheduled", run_key=run_key)
                        finally:
                            db.close()
        except Exception:  # noqa: BLE001 -- the scheduler loop itself must never die
            log.exception("auto_ingest scheduler tick failed (will retry next poll)")
        _stop_event.wait(settings.AUTO_INGEST_POLL_SECONDS)


def start_auto_ingest():
    """Starts the twice-daily scheduler as a daemon thread. No-op if
    AUTO_INGEST_ENABLED is false or the corpus file isn't present (e.g. a
    fresh checkout that hasn't run build_cloudtrail_corpus.py) -- logs why
    rather than silently doing nothing."""
    global _thread
    if not settings.AUTO_INGEST_ENABLED:
        log.info("AUTO_INGEST_ENABLED=false -- automatic re-ingestion scheduler not started")
        return
    if not os.path.exists(CORPUS_PATH):
        log.warning("corpus not found at %s -- automatic re-ingestion scheduler not started", CORPUS_PATH)
        return
    if _thread and _thread.is_alive():
        return
    slots = _parse_times(settings.AUTO_INGEST_TIMES)
    if not slots:
        log.warning("AUTO_INGEST_TIMES has no valid entries -- scheduler not started")
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, args=(slots,), daemon=True)
    _thread.start()
    log.info("auto-ingest scheduler started, slots=%s", slots)


def stop_auto_ingest():
    _stop_event.set()


def main():
    parser = argparse.ArgumentParser(description="ULPF automatic real-data re-ingestion")
    parser.add_argument("--once", action="store_true", help="run a single manual ingestion pass and exit")
    args = parser.parse_args()

    if args.once:
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            result = run_once(db, trigger="manual")
            print(json.dumps(result, indent=2))
        finally:
            db.close()
        return

    slots = _parse_times(settings.AUTO_INGEST_TIMES)
    log.info("running standalone scheduler, slots=%s", slots)
    _loop(slots)


if __name__ == "__main__":
    main()
