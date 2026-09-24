"""
Seed script for Universal Log Pre-processing Framework.
Run: python -m app.utils.seed
"""
import sys
import os
import uuid
import hashlib
import io
import json
from datetime import datetime, timezone, timedelta
import random

# Must run from /app in Docker, or from backend/ locally
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.core.database import SessionLocal, engine
from app.core.storage import get_minio_client, init_minio
from app.core.search import get_opensearch_client, init_opensearch
from app.core.config import settings
from app.models.all import Base, Source, MappingRegistry

SAMPLE_SOURCES = [
    {"id": "FW-001", "name": "Perimeter Firewall A", "vendor": "Cisco", "product": "ASA", "device_type": "firewall"},
    {"id": "FW-002", "name": "Perimeter Firewall B", "vendor": "Palo Alto", "product": "PAN-OS", "device_type": "firewall"},
    {"id": "IDS-001", "name": "IDS Sensor 1", "vendor": "Snort", "product": "Snort IDS", "device_type": "ids"},
    {"id": "AUTH-001", "name": "Active Directory Auth", "vendor": "Microsoft", "product": "AD", "device_type": "authentication"},
    {"id": "FW-PROP-001", "name": "Proprietary Firewall", "vendor": "XYZ Corp", "product": "XFW-v2", "device_type": "firewall"},
]

SAMPLE_MAPPINGS = [
    {"vendor": "Cisco", "device_type": "firewall", "raw_field": "src", "canonical_field": "source.ip", "mapping_type": "deterministic", "confidence": 1.0, "approved": True, "approved_by": "system"},
    {"vendor": "Cisco", "device_type": "firewall", "raw_field": "dst", "canonical_field": "destination.ip", "mapping_type": "deterministic", "confidence": 1.0, "approved": True, "approved_by": "system"},
    {"vendor": "Cisco", "device_type": "firewall", "raw_field": "sport", "canonical_field": "source.port", "mapping_type": "deterministic", "confidence": 1.0, "approved": True, "approved_by": "system"},
    {"vendor": "Cisco", "device_type": "firewall", "raw_field": "dport", "canonical_field": "destination.port", "mapping_type": "deterministic", "confidence": 1.0, "approved": True, "approved_by": "system"},
    {"vendor": "XYZ Corp", "device_type": "firewall", "raw_field": "peer", "canonical_field": "source.ip", "mapping_type": "manual", "confidence": 0.74, "approved": False, "approved_by": None},
]

# Synthetic logs representing the same "DENY SSH from 192.168.1.20 to 10.0.0.5" event in 4 vendor formats
SYNTHETIC_LOGS = [
    {
        "source_id": "FW-001",
        "format": "Syslog",
        "vendor": "Cisco",
        "log": "<134>Sep 22 16:45:32 FW-001 %ASA-3-106001: Inbound TCP connection denied from 192.168.1.20/51234 to 10.0.0.5/22 flags SYN  on interface outside",
        "event_type": "firewall_deny"
    },
    {
        "source_id": "FW-002",
        "format": "CEF",
        "vendor": "Palo Alto",
        "log": "CEF:0|Palo Alto Networks|PAN-OS|10.1|4000|Traffic Deny|7|src=192.168.1.20 dst=10.0.0.5 spt=51234 dpt=22 proto=TCP act=deny",
        "event_type": "firewall_deny"
    },
    {
        "source_id": "IDS-001",
        "format": "JSON",
        "vendor": "Snort",
        "log": json.dumps({
            "timestamp": "2026-09-22T16:45:32Z",
            "sourceAddress": "192.168.1.20",
            "destinationAddress": "10.0.0.5",
            "sourcePort": 51234,
            "destinationPort": 22,
            "action": "BLOCK",
            "protocol": "TCP",
            "severity": "HIGH"
        }),
        "event_type": "firewall_deny"
    },
    {
        "source_id": "FW-PROP-001",
        "format": "UNKNOWN",
        "vendor": "XYZ Corp",
        "log": "FW-D|22-09-2026 16:45:32|192.168.1.20>10.0.0.5|TCP|51234>22|BLOCK",
        "event_type": "firewall_deny"
    },
    # Login failures (attack sequence seed)
    {
        "source_id": "AUTH-001",
        "format": "CEF",
        "vendor": "Microsoft",
        "log": "CEF:0|Microsoft|AD|2019|4625|An account failed to log on|5|src=192.168.1.20 dst=10.0.0.5 spt=0 dpt=0 act=login_failure",
        "event_type": "login_failure"
    },
    {
        "source_id": "AUTH-001",
        "format": "CEF",
        "vendor": "Microsoft",
        "log": "CEF:0|Microsoft|AD|2019|4625|An account failed to log on|5|src=192.168.1.20 dst=10.0.0.5 spt=0 dpt=0 act=login_failure",
        "event_type": "login_failure"
    },
    {
        "source_id": "AUTH-001",
        "format": "CEF",
        "vendor": "Microsoft",
        "log": "CEF:0|Microsoft|AD|2019|4624|An account was successfully logged on|3|src=192.168.1.20 dst=10.0.0.5 spt=0 dpt=0 act=login_success",
        "event_type": "login_success"
    },
    {
        "source_id": "AUTH-001",
        "format": "JSON",
        "vendor": "Microsoft",
        "log": json.dumps({
            "event_id": "4672",
            "src": "192.168.1.20",
            "dst": "10.0.0.5",
            "action": "privilege_escalation",
            "severity": "CRITICAL",
            "description": "Special privileges assigned to new logon"
        }),
        "event_type": "privilege_escalation"
    }
]

def seed_canonical_event(os_client, source_id, raw_event_id, raw_sha256, log_entry):
    """Create a pre-built canonical event and index into OpenSearch directly."""
    actions = {
        "firewall_deny": ("deny", "HIGH", "network", "connection"),
        "login_failure": ("login_failure", "MEDIUM", "authentication", "start"),
        "login_success": ("login_success", "LOW", "authentication", "start"),
        "privilege_escalation": ("privilege_escalation", "CRITICAL", "authentication", "change"),
        "port_scan": ("port_scan", "HIGH", "network", "connection"),
    }
    
    evt_type = log_entry.get("event_type", "firewall_deny")
    action, severity, category, evt_kind = actions.get(evt_type, ("unknown", "LOW", "unknown", "unknown"))
    
    risk_map = {"LOW": 20, "MEDIUM": 45, "HIGH": 72, "CRITICAL": 91}
    risk_score = risk_map.get(severity, 20)
    
    risk_level_map = {"LOW": "LOW", "MEDIUM": "MEDIUM", "HIGH": "HIGH", "CRITICAL": "CRITICAL"}
    
    canonical = {
        "event_id": raw_event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": {
            "category": category,
            "type": evt_kind,
            "action": action,
            "severity": severity.lower(),
            "outcome": "failure" if "fail" in action else "success"
        },
        "source": {"ip": "192.168.1.20", "port": 51234},
        "destination": {"ip": "10.0.0.5", "port": 22},
        "network": {"protocol": "TCP", "transport": "TCP"},
        "device": {
            "id": source_id,
            "vendor": log_entry.get("vendor", "UNKNOWN"),
            "product": log_entry.get("format", "UNKNOWN")
        },
        "parser": {"format": log_entry.get("format", "UNKNOWN"), "parser_version": "1.0"},
        "normalization": {"mapping_method": "deterministic", "confidence": 0.97},
        "provenance": {"raw_event_id": raw_event_id, "raw_sha256": raw_sha256},
        "risk": {
            "score": risk_score,
            "level": risk_level_map.get(severity, "LOW"),
            "factors": [
                {"factor": "severity", "contribution": int(risk_score * 0.3)},
                {"factor": "action", "contribution": int(risk_score * 0.2)},
                {"factor": "frequency", "contribution": int(risk_score * 0.2)},
                {"factor": "asset_criticality", "contribution": int(risk_score * 0.15)},
                {"factor": "correlation", "contribution": int(risk_score * 0.15)}
            ]
        },
        "extensions": {}
    }
    
    os_client.index(index=settings.OPENSEARCH_INDEX, body=canonical, id=raw_event_id)
    return canonical

def main():
    print("🌱 Starting seed process...")
    
    db = SessionLocal()
    
    # Create tables (in case migrations weren't applied yet)
    Base.metadata.create_all(bind=engine)
    
    # Init storage
    try:
        init_minio()
        print("✅ MinIO bucket created.")
    except Exception as e:
        print(f"⚠️  MinIO: {e}")
    
    try:
        init_opensearch()
        print("✅ OpenSearch index created.")
    except Exception as e:
        print(f"⚠️  OpenSearch: {e}")

    minio_client = get_minio_client()
    os_client = get_opensearch_client()
    
    # Seed Sources
    for src in SAMPLE_SOURCES:
        existing = db.query(Source).filter(Source.id == src["id"]).first()
        if not existing:
            db.add(Source(**src))
    db.commit()
    print(f"✅ Seeded {len(SAMPLE_SOURCES)} sources.")
    
    # Seed Mapping Registry
    for m in SAMPLE_MAPPINGS:
        existing = db.query(MappingRegistry).filter(
            MappingRegistry.vendor == m["vendor"],
            MappingRegistry.raw_field == m["raw_field"]
        ).first()
        if not existing:
            db.add(MappingRegistry(**m))
    db.commit()
    print(f"✅ Seeded {len(SAMPLE_MAPPINGS)} mappings.")
    
    # Seed synthetic logs as raw events + canonical events
    from app.models.all import RawEventMetadata
    from datetime import timezone
    
    for log_entry in SYNTHETIC_LOGS:
        event_id = f"seed_{uuid.uuid4().hex[:12]}"
        raw_log = log_entry["log"]
        raw_sha256 = hashlib.sha256(raw_log.encode('utf-8')).hexdigest()
        raw_bytes = raw_log.encode('utf-8')
        received_at = datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 120))
        date_path = received_at.strftime("%Y/%m/%d")
        raw_location = f"{date_path}/{event_id}.txt"
        
        # Store in MinIO
        try:
            minio_client.put_object(
                settings.MINIO_RAW_BUCKET,
                raw_location,
                io.BytesIO(raw_bytes),
                length=len(raw_bytes),
                content_type="text/plain"
            )
        except Exception as e:
            print(f"⚠️  Could not store raw event in MinIO: {e}")
        
        # Store metadata in Postgres
        meta = RawEventMetadata(
            event_id=event_id,
            source_id=log_entry["source_id"],
            received_at=received_at,
            ingestion_protocol="seed",
            raw_sha256=raw_sha256,
            raw_location=raw_location,
            processing_status="processed"
        )
        db.add(meta)
        
        # Index canonical event in OpenSearch
        try:
            seed_canonical_event(os_client, log_entry["source_id"], event_id, raw_sha256, log_entry)
        except Exception as e:
            print(f"⚠️  Could not index to OpenSearch: {e}")
    
    db.commit()
    print(f"✅ Seeded {len(SYNTHETIC_LOGS)} synthetic log events.")
    print("🎉 Seed complete! The dashboard should now be populated.")

if __name__ == "__main__":
    main()
