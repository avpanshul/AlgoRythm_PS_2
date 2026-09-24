from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime

# Caps for ingestion payloads. Chosen to comfortably fit real single log lines/records
# (syslog, CEF, JSON events, multi-line stack traces) while bounding disk/DB writes.
MAX_SINGLE_LOG_BYTES = 1 * 1024 * 1024       # 1 MB per raw log
MAX_SOURCE_ID_LENGTH = 128
MAX_BATCH_SIZE = 500                          # max number of logs per batch request
MAX_BATCH_TOTAL_BYTES = 20 * 1024 * 1024      # 20 MB combined per batch request


class IngestEventRequest(BaseModel):
    source_id: Optional[str] = Field(default="UNKNOWN", max_length=MAX_SOURCE_ID_LENGTH)
    raw_log: str = Field(..., min_length=1, max_length=MAX_SINGLE_LOG_BYTES)


class BatchIngestRequest(BaseModel):
    source_id: Optional[str] = Field(default="UNKNOWN", max_length=MAX_SOURCE_ID_LENGTH)
    raw_logs: List[str] = Field(..., min_length=1, max_length=MAX_BATCH_SIZE)

    @field_validator("raw_logs")
    @classmethod
    def validate_raw_logs(cls, logs: List[str]) -> List[str]:
        total_bytes = 0
        for log in logs:
            if not log:
                raise ValueError("raw_logs entries must not be empty")
            log_bytes = len(log.encode("utf-8"))
            if log_bytes > MAX_SINGLE_LOG_BYTES:
                raise ValueError(f"each raw log must be <= {MAX_SINGLE_LOG_BYTES} bytes")
            total_bytes += log_bytes
        if total_bytes > MAX_BATCH_TOTAL_BYTES:
            raise ValueError(f"batch total size must be <= {MAX_BATCH_TOTAL_BYTES} bytes")
        return logs

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
