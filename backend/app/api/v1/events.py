from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.all import NormalizedEvent, RawEventMetadata, NormalizedEventVersion, User, AuditLog
from app.core.local_storage import read_raw_log

router = APIRouter()

@router.get("/events")
def list_events(
    q: Optional[str] = Query(None, description="Search query"),
    severity: Optional[str] = None,
    risk_level: Optional[str] = None,
    source_id: Optional[str] = None,
    since_hours: Optional[float] = Query(None, description="Only events with a real timestamp within the last N hours"),
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(NormalizedEvent)

    if source_id:
        query = query.filter(NormalizedEvent.source_id == source_id)
    if q:
        # Real bug fixed: the Log Explorer's own placeholder text says
        # "Search by IP, user, hash..." but user_name was never actually
        # included in the search -- a query for a real username silently
        # matched nothing.
        query = query.filter(
            or_(
                NormalizedEvent.message.ilike(f"%{q}%"),
                NormalizedEvent.source_ip.ilike(f"%{q}%"),
                NormalizedEvent.dest_ip.ilike(f"%{q}%"),
                NormalizedEvent.action.ilike(f"%{q}%"),
                NormalizedEvent.user_name.ilike(f"%{q}%"),
                NormalizedEvent.raw_sha256.ilike(f"%{q}%"),
            )
        )
    if severity:
        query = query.filter(NormalizedEvent.severity == severity.lower())
    if risk_level:
        query = query.filter(NormalizedEvent.risk_level == risk_level.upper())
    if since_hours is not None:
        query = query.filter(NormalizedEvent.timestamp >= datetime.now(timezone.utc) - timedelta(hours=since_hours))

    total = query.count()
    items = query.order_by(NormalizedEvent.timestamp.desc()).offset((page - 1) * size).limit(size).all()
    
    return {
        "total": total,
        "page": page,
        "size": size,
        "events": [item.canonical_json for item in items if item.canonical_json]
    }

@router.get("/vault")
def list_vault(
    q: Optional[str] = Query(None, description="Search by event ID or SHA-256"),
    source_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List raw-log vault records (bronze tier) -- the cold, unparsed store each
    normalized event links back to by raw_sha256/raw_location."""
    query = db.query(RawEventMetadata)
    if q:
        query = query.filter(
            or_(RawEventMetadata.event_id.ilike(f"%{q}%"), RawEventMetadata.raw_sha256.ilike(f"%{q}%"))
        )
    if source_id:
        query = query.filter(RawEventMetadata.source_id == source_id)

    total = query.count()
    items = query.order_by(RawEventMetadata.received_at.desc()).offset((page - 1) * size).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "event_id": m.event_id,
                "source_id": m.source_id,
                "received_at": m.received_at.isoformat() if m.received_at else None,
                "ingestion_protocol": m.ingestion_protocol,
                "raw_sha256": m.raw_sha256,
                "raw_location": m.raw_location,
                "processing_status": m.processing_status,
            }
            for m in items
        ],
    }


@router.get("/vault/{event_id}")
def get_vault_record(event_id: str, db: Session = Depends(get_db)):
    meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == event_id).first()
    if not meta:
        raise HTTPException(status_code=404, detail="Raw event not found")

    try:
        raw_content = read_raw_log(meta.raw_location)
    except Exception:
        raw_content = None

    return {
        "event_id": meta.event_id,
        "source_id": meta.source_id,
        "received_at": meta.received_at.isoformat() if meta.received_at else None,
        "ingestion_protocol": meta.ingestion_protocol,
        "raw_sha256": meta.raw_sha256,
        "raw_location": meta.raw_location,
        "processing_status": meta.processing_status,
        "raw_content": raw_content,
        "size_bytes": len(raw_content.encode("utf-8")) if raw_content else None,
    }


@router.get("/events/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).first()
    if not event or not event.canonical_json:
        raise HTTPException(status_code=404, detail="Event not found")
    return event.canonical_json

@router.get("/events/{event_id}/raw")
def get_raw_event(event_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns the unredacted raw log for this event (app/core/processing.py
    only redacts the *derived* `message` field on the canonical event -- the
    raw vault has always held the original, unmasked content). Part D9: this
    is exactly the "view unmasked" action, so it requires a real login (the
    rest of the events router stays open per main.py's deliberate demo
    read-view carve-out) and is written to the audit log on every call --
    not just logged in principle, a real AuditLog row per view, same
    hash-chained table every other admin action uses."""
    meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == event_id).first()
    if not meta:
        raise HTTPException(status_code=404, detail="Raw event not found")

    try:
        raw_content = read_raw_log(meta.raw_location)
        db.add(AuditLog(user=current_user.id, action="event_raw_unmasked", entity_type="NormalizedEvent", entity_id=event_id))
        db.commit()
        return {
            "event_id": event_id,
            "raw_sha256": meta.raw_sha256,
            "raw_location": meta.raw_location,
            "received_at": meta.received_at.isoformat() if meta.received_at else None,
            "ingestion_protocol": meta.ingestion_protocol,
            "raw_content": raw_content
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not retrieve raw event: {e}")

@router.get("/events/{event_id}/trace")
def trace_event(event_id: str, db: Session = Depends(get_db)):
    """Return full provenance chain from canonical -> raw"""
    canonical = db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).first()
    canonical_data = canonical.canonical_json if canonical else None
    
    meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == event_id).first()
    
    raw_content = None
    if meta:
        try:
            raw_content = read_raw_log(meta.raw_location)
        except Exception:
            raw_content = "Could not retrieve"
    
    return {
        "event_id": event_id,
        "trace": [
            {
                "stage": "1_raw_ingestion",
                "label": "Raw Log Received",
                "data": {
                    "raw_content": raw_content,
                    "sha256": meta.raw_sha256 if meta else None,
                    "protocol": meta.ingestion_protocol if meta else None,
                    "storage": meta.raw_location if meta else None,
                }
            },
            {
                "stage": "2_format_detection",
                "label": "Format Detected",
                "data": {"format": canonical_data.get("parser", {}).get("format") if canonical_data else "UNKNOWN"}
            },
            {
                "stage": "3_parsing",
                "label": "Deterministic Parsing",
                "data": {"parser_version": canonical_data.get("parser", {}).get("parser_version") if canonical_data else None}
            },
            {
                "stage": "4_normalization",
                "label": "Canonical Normalization",
                "data": {
                    "mapping_method": canonical_data.get("normalization", {}).get("mapping_method") if canonical_data else None,
                    "confidence": canonical_data.get("normalization", {}).get("confidence") if canonical_data else None
                }
            },
            {
                "stage": "5_canonical_event",
                "label": "Canonical Event",
                "data": canonical_data
            },
            {
                "stage": "6_risk_scoring",
                "label": "Risk Score",
                "data": canonical_data.get("risk") if canonical_data else None
            }
        ]
    }

@router.get("/events/{event_id}/versions")
def get_event_versions(event_id: str, db: Session = Depends(get_db)):
    """Real replay history for one event -- every prior normalization
    archived before a replay job overwrote it (see app/api/v1/replay.py),
    newest first. Never fabricated: an event replay has never touched
    returns an honest empty list."""
    versions = (
        db.query(NormalizedEventVersion)
        .filter(NormalizedEventVersion.event_id == event_id)
        .order_by(NormalizedEventVersion.archived_at.desc())
        .all()
    )
    return [
        {
            "id": v.id, "superseded_by_replay_job_id": v.superseded_by_replay_job_id,
            "parser_id": v.parser_id, "parser_version": v.parser_version,
            "mapping_method": v.mapping_method, "risk_score": v.risk_score, "risk_level": v.risk_level,
            "normalized_sha256": v.normalized_sha256, "archived_at": v.archived_at,
        }
        for v in versions
    ]


@router.post("/reprocess/{event_id}")
def reprocess_event(event_id: str, db: Session = Depends(get_db)):
    meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == event_id).first()
    if not meta:
        raise HTTPException(status_code=404, detail="Event not found")
    
    try:
        from app.core.processing import process_raw_event
        raw_content = read_raw_log(meta.raw_location)
        process_raw_event(db, event_id, raw_content, meta.source_id or "UNKNOWN", meta.raw_sha256, meta.raw_location)
        meta.processing_status = "reprocessed"
        db.commit()
        return {"status": "reprocessed", "event_id": event_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reprocess: {str(e)}")
