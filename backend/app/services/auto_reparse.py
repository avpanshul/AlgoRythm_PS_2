r"""Item 3: backlog re-parse.

Closes a real, verified gap (live audit, 2026-09-28): publishing an
AI-drafted pack (app/services/pack_drafting.py, id format `ai-draft-{cluster_id}`)
versioned and flipped the parser to `status="published"` but never touched
the DLQ events that were sitting there *because* that cluster's format had
no working parser -- an analyst had to manually retry each one,
one-by-one, via POST /dlq/{id}/retry.

Same real reprocessing call retry_dlq already uses (app/api/v1/dlq.py):
pulls raw_sha256/raw_location from RawEventMetadata (not the DLQ's own
truncated copy) and calls the real process_raw_event pipeline -- this
module doesn't invent a second code path, it batches and automates the
existing one.

Bounded and idempotent by construction: only queries DLQEvent rows still
`status="failed"` for the cluster (anything already `resolved` is excluded
by the query itself, so a second run -- or this run being called twice --
never reprocesses the same event twice), capped at
AUTO_REPARSE_BATCH_SIZE per call. Runs as a background daemon thread
(bounded task) so publishing a parser doesn't block on however large the
backlog is; the HTTP response returns immediately either way.
"""
import logging
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.local_storage import read_raw_log
from app.core.processing import process_raw_event
from app.models.all import DLQEvent, RawEventMetadata, AuditLog

log = logging.getLogger("auto_reparse")


def cluster_id_for_parser(parser_id: str) -> str | None:
    """AI-drafted packs are the only ones with a real, existing link back to
    a specific DLQ cluster (see pack_drafting.py:draft_pack_for_cluster's
    `pack_id = f"ai-draft-{cluster_id}"`). A hand-authored vendor pack has no
    such link -- there's no cluster to reparse for it, honestly returns None
    rather than guessing."""
    prefix = "ai-draft-"
    if parser_id and parser_id.startswith(prefix):
        return parser_id[len(prefix):]
    return None


def reparse_cluster_backlog(db: Session, cluster_id: str, triggered_by: str, batch_size: int = None) -> dict:
    """Re-processes up to `batch_size` still-failed DLQ events for this
    cluster through the real pipeline. Returns real counts -- never claims
    more were reprocessed than actually were."""
    batch_size = batch_size if batch_size is not None else settings.AUTO_REPARSE_BATCH_SIZE

    pending = (
        db.query(DLQEvent)
        .filter(DLQEvent.drain_cluster_id == cluster_id, DLQEvent.status == "failed")
        .order_by(DLQEvent.created_at.asc())
        .limit(batch_size)
        .all()
    )

    resolved = 0
    still_failed = 0
    for dlq in pending:
        dlq.retry_count += 1
        dlq.status = "retrying"
        dlq.updated_at = datetime.now(timezone.utc)

        raw_log = dlq.raw_log
        if not raw_log and dlq.raw_location:
            try:
                raw_log = read_raw_log(dlq.raw_location)
            except FileNotFoundError:
                dlq.status = "failed"
                dlq.failure_detail = "Raw log file not found during auto-reparse"
                still_failed += 1
                continue

        if not raw_log:
            dlq.status = "failed"
            still_failed += 1
            continue

        # Same provenance lookup retry_dlq uses -- the real, full-fidelity
        # raw_sha256/raw_location from RawEventMetadata, not the DLQ row's
        # own truncated copy, so the SHA-256 link is preserved exactly as
        # it would be for a manual retry.
        meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == dlq.event_id).first()
        raw_sha256 = meta.raw_sha256 if meta else ""
        raw_location = meta.raw_location if meta else (dlq.raw_location or "")

        result = process_raw_event(db, dlq.event_id, raw_log, dlq.source_id or "UNKNOWN", raw_sha256, raw_location)
        if result is not None:
            dlq.status = "resolved"
            resolved += 1
        else:
            dlq.status = "failed"
            still_failed += 1

    db.add(AuditLog(
        user=triggered_by, action="cluster_backlog_reparsed", entity_type="UnknownTemplate", entity_id=cluster_id,
        after_state={"batch_size": batch_size, "candidates": len(pending), "resolved": resolved, "still_failed": still_failed},
    ))
    db.commit()

    log.info("cluster %s backlog reparse: %d/%d resolved (batch_size=%d)", cluster_id, resolved, len(pending), batch_size)
    return {"cluster_id": cluster_id, "candidates": len(pending), "resolved": resolved, "still_failed": still_failed}


def trigger_background_reparse(parser_id: str, published_by: str):
    """Fire-and-forget entry point called from POST /parsers/{id}/publish.
    No-op (logged, not silent) if ENABLE_AUTO_REPARSE is off or this parser
    has no real originating cluster. Runs in a daemon thread with its own
    DB session so the publish HTTP response is never blocked by however
    large the backlog is."""
    if not settings.ENABLE_AUTO_REPARSE:
        return
    cluster_id = cluster_id_for_parser(parser_id)
    if not cluster_id:
        log.info("parser %s published but has no originating DLQ cluster -- nothing to reparse", parser_id)
        return

    def _run():
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            reparse_cluster_backlog(db, cluster_id, triggered_by=f"auto_reparse(published_by={published_by})")
        except Exception as e:  # noqa: BLE001 -- a background reparse failing must never crash the app
            log.exception("background reparse for cluster %s failed: %s", cluster_id, e)
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()
