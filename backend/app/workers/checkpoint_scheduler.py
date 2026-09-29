"""Issues a signed Merkle checkpoint on a fixed interval instead of after every
event. Run this (with AUTO_CHECKPOINT_EVERY_EVENT=false, see core/config.py)
once ingestion volume outgrows what per-event checkpointing can keep up with --
create_checkpoint() is O(n) in the number of leaves, so per-event checkpointing
makes total ingestion cost O(n^2) (measured in docs/benchmarks.md).

Usage:
    python -m app.workers.checkpoint_scheduler --interval-seconds 30
"""
import argparse
import logging
import threading
import time

from app.core.database import SessionLocal
from app.integrity import service as integrity_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] checkpoint_scheduler: %(message)s")
log = logging.getLogger("checkpoint_scheduler")

_reverify_stop_event = threading.Event()
_reverify_thread = None


def run_reverify_once(db=None):
    """Re-verifies a batch of due checkpoints (see
    integrity_service.reverify_due_checkpoints' docstring). Split out from
    run_once() so it can run on its own schedule, independent of whether
    checkpoints are being issued by THIS scheduler or per-event by the main
    pipeline (AUTO_CHECKPOINT_EVERY_EVENT=true, the default) -- reverify_due
    is meaningless work when tied only to a scheduler an operator might
    never run."""
    owns_session = db is None
    db = db or SessionLocal()
    try:
        results = integrity_service.reverify_due_checkpoints(db)
        for r in results:
            if r["status"] == "tamper_detected":
                log.error("TAMPER DETECTED on checkpoint id=%s: %s", r["checkpoint_id"], r["detail"])
            else:
                log.info("re-verified checkpoint id=%s: %s", r["checkpoint_id"], r["status"])
        return results
    finally:
        if owns_session:
            db.close()


def run_once():
    db = SessionLocal()
    try:
        checkpoint = integrity_service.create_checkpoint(db)
        log.info("issued checkpoint id=%s tree_size=%s root=%s", checkpoint.id, checkpoint.tree_size, checkpoint.root_hash[:16])
        run_reverify_once(db)
    finally:
        db.close()


def _reverify_loop(interval_seconds: int):
    while not _reverify_stop_event.is_set():
        try:
            run_reverify_once()
        except Exception:
            log.exception("scheduled checkpoint re-verification failed (will retry next interval)")
        _reverify_stop_event.wait(interval_seconds)


def start_background_reverification(interval_seconds: int = 3600):
    """Starts scheduled checkpoint self-verification as an always-on daemon
    thread, independent of AUTO_CHECKPOINT_EVERY_EVENT and independent of
    whether this module is ever run standalone as a worker process --
    without this, a deployment using the (default) per-event checkpoint
    issuance path would never re-walk old checkpoints at all. Cheap to poll
    hourly: reverify_due_checkpoints only actually does work for checkpoints
    past CHECKPOINT_REVERIFY_INTERVAL_HOURS (default 24h)."""
    global _reverify_thread
    if _reverify_thread and _reverify_thread.is_alive():
        return
    _reverify_stop_event.clear()
    _reverify_thread = threading.Thread(target=_reverify_loop, args=(interval_seconds,), daemon=True)
    _reverify_thread.start()
    log.info("background checkpoint re-verification started (%ds poll interval)", interval_seconds)


def stop_background_reverification():
    _reverify_stop_event.set()


def main():
    parser = argparse.ArgumentParser(description="ULPF Merkle checkpoint scheduler")
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--once", action="store_true", help="issue a single checkpoint and exit")
    args = parser.parse_args()

    if args.once:
        run_once()
        return

    log.info("checkpointing every %ds", args.interval_seconds)
    while True:
        try:
            run_once()
        except Exception:
            log.exception("checkpoint attempt failed")
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
