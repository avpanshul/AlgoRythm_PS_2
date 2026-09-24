from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.all import NormalizedEvent, RawEventMetadata
from app.core.local_storage import read_raw_log

router = APIRouter()

@router.get("/events")
def list_events(
    q: Optional[str] = Query(None, description="Search query"),
    severity: Optional[str] = None,
    risk_level: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(NormalizedEvent)
    
    if q:
        query = query.filter(
            or_(
                NormalizedEvent.message.ilike(f"%{q}%"),
                NormalizedEvent.source_ip.ilike(f"%{q}%"),
                NormalizedEvent.dest_ip.ilike(f"%{q}%"),
                NormalizedEvent.action.ilike(f"%{q}%")
            )
        )
    if severity:
        query = query.filter(NormalizedEvent.severity == severity.lower())
    if risk_level:
        query = query.filter(NormalizedEvent.risk_level == risk_level.upper())
    
    total = query.count()
    items = query.order_by(NormalizedEvent.timestamp.desc()).offset((page - 1) * size).limit(size).all()
    
    return {
        "total": total,
        "page": page,
        "size": size,
        "events": [item.canonical_json for item in items if item.canonical_json]
    }

@router.get("/events/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).first()
    if not event or not event.canonical_json:
        raise HTTPException(status_code=404, detail="Event not found")
    return event.canonical_json

@router.get("/events/{event_id}/raw")
def get_raw_event(event_id: str, db: Session = Depends(get_db)):
    meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == event_id).first()
    if not meta:
        raise HTTPException(status_code=404, detail="Raw event not found")
    
    try:
        raw_content = read_raw_log(meta.raw_location)
        return {
            "event_id": event_id,
            "raw_sha256": meta.raw_sha256,
            "raw_location": meta.raw_location,
            "received_at": meta.received_at.isoformat() if meta.received_at else None,
            "ingestion_protocol": meta.ingestion_protocol,
            "raw_content": raw_content
        }
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
