"""Dead-letter queue CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.all import DLQEvent, AuditLog, RawEventMetadata
from app.core.processing import process_raw_event
from app.core.local_storage import read_raw_log

router = APIRouter()


class AssignRequest(BaseModel):
    assigned_to: str


@router.get("/dlq")
def list_dlq(
    status: Optional[str] = None,
    reason: Optional[str] = None,
    source_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(DLQEvent)
    if status:
        q = q.filter(DLQEvent.status == status)
    if reason:
        q = q.filter(DLQEvent.failure_reason.ilike(f"%{reason}%"))
    if source_id:
        q = q.filter(DLQEvent.source_id == source_id)

    total = q.count()
    items = q.order_by(DLQEvent.created_at.desc()).offset((page - 1) * size).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": d.id,
                "event_id": d.event_id,
                "source_id": d.source_id,
                "failure_reason": d.failure_reason,
                "failure_detail": d.failure_detail,
                "parser_id": d.parser_id,
                "parser_version": d.parser_version,
                "retry_count": d.retry_count,
                "status": d.status,
                "assigned_to": d.assigned_to,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in items
        ],
    }


@router.post("/dlq/{dlq_id}/retry")
def retry_dlq(dlq_id: int, db: Session = Depends(get_db)):
    dlq = db.query(DLQEvent).filter(DLQEvent.id == dlq_id).first()
    if not dlq:
        raise HTTPException(status_code=404, detail="DLQ event not found")

    dlq.retry_count += 1
    dlq.status = "retrying"
    dlq.updated_at = datetime.now(timezone.utc)

    # Try to re-process
    raw_log = dlq.raw_log
    if not raw_log and dlq.raw_location:
        try:
            raw_log = read_raw_log(dlq.raw_location)
        except FileNotFoundError:
            dlq.status = "failed"
            dlq.failure_detail = "Raw log file not found for retry"
            db.commit()
            raise HTTPException(status_code=404, detail="Raw log file not found")

    if raw_log:
        meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == dlq.event_id).first()
        raw_sha256 = meta.raw_sha256 if meta else ""
        raw_location = meta.raw_location if meta else dlq.raw_location or ""

        result = process_raw_event(
            db, dlq.event_id, raw_log, dlq.source_id or "UNKNOWN",
            raw_sha256, raw_location, dlq.parser_id, dlq.parser_version
        )
        if result:
            dlq.status = "resolved"
            db.commit()
            return {"status": "resolved", "event_id": dlq.event_id}

    dlq.status = "failed"
    db.commit()

    audit = AuditLog(user="system", action="dlq_retry", entity_type="DLQEvent", entity_id=str(dlq_id))
    db.add(audit)
    db.commit()

    return {"status": "retry_failed", "dlq_id": dlq_id, "retry_count": dlq.retry_count}


@router.post("/dlq/{dlq_id}/resolve")
def resolve_dlq(dlq_id: int, db: Session = Depends(get_db)):
    dlq = db.query(DLQEvent).filter(DLQEvent.id == dlq_id).first()
    if not dlq:
        raise HTTPException(status_code=404, detail="DLQ event not found")

    dlq.status = "resolved"
    dlq.updated_at = datetime.now(timezone.utc)

    audit = AuditLog(user="admin", action="dlq_resolved", entity_type="DLQEvent", entity_id=str(dlq_id))
    db.add(audit)
    db.commit()

    return {"status": "resolved", "dlq_id": dlq_id}


@router.post("/dlq/{dlq_id}/assign")
def assign_dlq(dlq_id: int, req: AssignRequest, db: Session = Depends(get_db)):
    dlq = db.query(DLQEvent).filter(DLQEvent.id == dlq_id).first()
    if not dlq:
        raise HTTPException(status_code=404, detail="DLQ event not found")

    dlq.assigned_to = req.assigned_to
    dlq.status = "assigned"
    dlq.updated_at = datetime.now(timezone.utc)

    audit = AuditLog(
        user="admin", action="dlq_assigned", entity_type="DLQEvent",
        entity_id=str(dlq_id), after_state={"assigned_to": req.assigned_to}
    )
    db.add(audit)
    db.commit()

    return {"status": "assigned", "dlq_id": dlq_id, "assigned_to": req.assigned_to}
