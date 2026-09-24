from pydantic import BaseModel, IPvAnyAddress, Field
from typing import Optional, Dict, Any
from datetime import datetime

class EventDetails(BaseModel):
    category: Optional[str] = "unknown"
    type: Optional[str] = "unknown"
    action: Optional[str] = "unknown"
    severity: Optional[str] = "unknown"
    outcome: Optional[str] = "unknown"

class Endpoint(BaseModel):
    ip: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)

class NetworkDetails(BaseModel):
    protocol: Optional[str] = None
    transport: Optional[str] = None

class DeviceDetails(BaseModel):
    id: Optional[str] = None
    vendor: Optional[str] = None
    product: Optional[str] = None

class ParserInfo(BaseModel):
    format: str
    parser_version: str = "1.0"

class NormalizationInfo(BaseModel):
    mapping_method: str
    confidence: float

class ProvenanceInfo(BaseModel):
    raw_event_id: str
    raw_sha256: str

class CanonicalEvent(BaseModel):
    event_id: str
    timestamp: str
    event: EventDetails = EventDetails()
    source: Endpoint = Endpoint()
    destination: Endpoint = Endpoint()
    network: NetworkDetails = NetworkDetails()
    device: DeviceDetails = DeviceDetails()
    user: Optional[Dict[str, Any]] = None
    parser: ParserInfo
    normalization: NormalizationInfo
    provenance: ProvenanceInfo
    extensions: Optional[Dict[str, Any]] = {}
