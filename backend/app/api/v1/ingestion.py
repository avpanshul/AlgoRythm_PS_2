import uuid
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.local_storage import save_raw_log
from app.core.processing import process_raw_event
from app.models.all import RawEventMetadata
from app.schemas.events import (
    IngestEventRequest,
    BatchIngestRequest,
    RawEventResponse,
    MAX_SINGLE_LOG_BYTES,
)

router = APIRouter()

def process_single_log(db: Session, raw_log: str, source_id: str, protocol: str) -> RawEventMetadata:
    event_id = f"evt_{uuid.uuid4().hex}"
    raw_sha256 = hashlib.sha256(raw_log.encode('utf-8')).hexdigest()
    received_at = datetime.now(timezone.utc)
    
    # Define location in local storage (year/month/day/event_id.txt)
    date_path = received_at.strftime("%Y/%m/%d")
    raw_location = f"{date_path}/{event_id}.txt"
    
    # Save to local storage
    save_raw_log(raw_location, raw_log)
    
    # Save metadata to DB
    metadata = RawEventMetadata(
        event_id=event_id,
        source_id=source_id,
        received_at=received_at,
        ingestion_protocol=protocol,
        raw_sha256=raw_sha256,
        raw_location=raw_location,
        processing_status="processing"
    )
    db.add(metadata)
    db.commit()
    db.refresh(metadata)
    
    # Run full processing pipeline synchronously for the demo
    process_raw_event(db, event_id, raw_log, source_id, raw_sha256, raw_location)
    
    db.refresh(metadata)
    return metadata

@router.post("/events", response_model=RawEventResponse)
def ingest_event(req: IngestEventRequest, db: Session = Depends(get_db)):
    return process_single_log(db, req.raw_log, req.source_id, "http")

@router.post("/events/batch", response_model=dict)
def ingest_batch(req: BatchIngestRequest, db: Session = Depends(get_db)):
    events = []
    for log in req.raw_logs:
        meta = process_single_log(db, log, req.source_id, "http")
        events.append(meta.event_id)
    return {"status": "success", "ingested": len(events), "event_ids": events}

@router.post("/ingest/syslog", response_model=RawEventResponse)
async def ingest_syslog_raw(request: Request, db: Session = Depends(get_db)):
    body_bytes = await request.body()
    if len(body_bytes) > MAX_SINGLE_LOG_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Payload too large (max {MAX_SINGLE_LOG_BYTES} bytes)",
        )
    try:
        raw_log = body_bytes.decode('utf-8').strip()
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Payload must be valid UTF-8 text")
    if not raw_log:
        raise HTTPException(status_code=400, detail="Empty payload")

    return process_single_log(db, raw_log, "UNKNOWN", "syslog-http")
