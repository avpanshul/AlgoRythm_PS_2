from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class IngestEventRequest(BaseModel):
    source_id: Optional[str] = "UNKNOWN"
    raw_log: str

class BatchIngestRequest(BaseModel):
    source_id: Optional[str] = "UNKNOWN"
    raw_logs: List[str]

class RawEventResponse(BaseModel):
    event_id: str
    source_id: str
    received_at: datetime
    ingestion_protocol: str
    raw_sha256: str
    raw_location: str
    processing_status: str

    class Config:
        from_attributes = True
