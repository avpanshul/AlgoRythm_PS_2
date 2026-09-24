"""Storage API."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
import os

from app.core.database import get_db
from app.models.all import NormalizedEvent, RawEventMetadata
from app.core.local_storage import get_storage_size_bytes, get_file_count

router = APIRouter()

@router.get("/storage/summary")
def get_storage_summary(db: Session = Depends(get_db)):
    total_raw = db.query(func.count(RawEventMetadata.event_id)).scalar() or 0
    total_normalized = db.query(func.count(NormalizedEvent.event_id)).scalar() or 0
    
    raw_size_bytes = get_storage_size_bytes()
    # Estimate normalized size based on rows
    normalized_size_bytes = total_normalized * 1500  # Approx 1.5KB per record
    
    return {
        "raw_event_count": total_raw,
        "normalized_event_count": total_normalized,
        "metadata_count": total_raw,
        "raw_storage_size_bytes": raw_size_bytes,
        "normalized_storage_size_bytes": normalized_size_bytes,
        "total_storage_size_bytes": raw_size_bytes + normalized_size_bytes,
        "storage_health": "healthy",
        "last_backup": None,  # Simulated
        "raw_file_count": get_file_count(),
        "backend": "local_filesystem"
    }
