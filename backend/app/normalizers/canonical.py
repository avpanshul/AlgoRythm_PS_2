from sqlalchemy.orm import Session
from app.schemas.canonical import CanonicalEvent, EventDetails, Endpoint, NetworkDetails, DeviceDetails, ParserInfo, NormalizationInfo, ProvenanceInfo
from app.services.mapping_service import resolve_field_mapping
from app.core.config import settings

def normalize_event(db: Session, parsed_data: dict, raw_event_meta: dict, format_info: dict) -> CanonicalEvent:
    vendor = parsed_data.get("header", {}).get("vendor", "UNKNOWN")
    device_type = parsed_data.get("header", {}).get("product", "UNKNOWN")
    
    # We will build up the nested fields based on mapping
    canonical = {
        "event_id": raw_event_meta["event_id"],
        "timestamp": raw_event_meta["received_at"], # ISO format
        "event": {},
        "source": {},
        "destination": {},
        "network": {},
        "device": {
            "vendor": vendor,
            "product": device_type
        },
        "extensions": {}
    }
    
    min_confidence = 1.0
    mapping_methods = set()
    
    fields = parsed_data.get("fields", parsed_data)
    if isinstance(fields, dict):
        for k, v in fields.items():
            if isinstance(v, (dict, list)):
                canonical["extensions"][k] = v
                continue
                
            mapping = resolve_field_mapping(db, vendor, device_type, k, str(v), str(parsed_data))
            can_field = mapping["canonical_field"]
            conf = mapping["confidence"]
            method = mapping["mapping_type"]
            
            if conf < min_confidence:
                min_confidence = conf
            mapping_methods.add(method)
            
            # Map into nested dict
            if can_field.startswith("source."):
                canonical["source"][can_field.split('.')[1]] = v
            elif can_field.startswith("destination."):
                canonical["destination"][can_field.split('.')[1]] = v
            elif can_field.startswith("event."):
                canonical["event"][can_field.split('.')[1]] = v
            elif can_field.startswith("network."):
                canonical["network"][can_field.split('.')[1]] = v
            else:
                canonical["extensions"][k] = v

    # Type casting for ports
    for ep in ["source", "destination"]:
        if "port" in canonical[ep]:
            try:
                canonical[ep]["port"] = int(canonical[ep]["port"])
            except ValueError:
                canonical[ep].pop("port")
    
    return CanonicalEvent(
        event_id=canonical["event_id"],
        timestamp=canonical["timestamp"],
        event=EventDetails(**canonical["event"]),
        source=Endpoint(**canonical["source"]),
        destination=Endpoint(**canonical["destination"]),
        network=NetworkDetails(**canonical["network"]),
        device=DeviceDetails(**canonical["device"]),
        parser=ParserInfo(format=format_info["format"]),
        normalization=NormalizationInfo(
            mapping_method=",".join(mapping_methods) if mapping_methods else "deterministic",
            confidence=min_confidence
        ),
        provenance=ProvenanceInfo(
            raw_event_id=raw_event_meta["event_id"],
            raw_sha256=raw_event_meta["raw_sha256"]
        ),
        extensions=canonical["extensions"]
    )
