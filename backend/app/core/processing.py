"""
Synchronous log processing pipeline.
Replaces the Kafka consumer worker for the demo.

Pipeline stages:
  1. Format Detection
  2. Parsing (deterministic)
  3. Normalization to ECS-like schema
  4. PII Redaction
  5. Risk Scoring
  6. SHA-256 Integrity Hash
  7. Store normalized event in PostgreSQL
  8. Audit log entry
"""
import uuid
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.parsers.format_detector import detect_format
from app.parsers.deterministic import parse_log
from app.models.all import NormalizedEvent, DLQEvent, AuditLog, RawEventMetadata


# ─── PII Redaction Patterns ───────────────────────────────────────

PII_PATTERNS = [
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]', 'email'),
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[REDACTED_AADHAAR]', 'aadhaar'),
    (r'\b(?:\+91[\s-]?)?[6-9]\d{9}\b', '[REDACTED_PHONE]', 'phone'),
    (r'\bPAN[A-Z]{2}\d{4}[A-Z]\b', '[REDACTED_PAN]', 'pan'),
]


def redact_pii(text: str) -> Tuple[str, list]:
    """Apply PII redaction patterns. Returns (redacted_text, list_of_redacted_fields)."""
    redacted_fields = []
    result = text
    for pattern, replacement, field_type in PII_PATTERNS:
        matches = re.findall(pattern, result)
        if matches:
            result = re.sub(pattern, replacement, result)
            redacted_fields.append({"type": field_type, "count": len(matches)})
    return result, redacted_fields


def compute_risk_score(event_data: dict, source_ip: str = None) -> Tuple[int, str]:
    """Compute a simple risk score based on event severity and action."""
    severity = (event_data.get("severity") or "unknown").lower()
    action = (event_data.get("action") or "unknown").lower()

    score = 20  # base

    severity_map = {"critical": 40, "high": 30, "medium": 15, "low": 5, "info": 0}
    score += severity_map.get(severity, 10)

    # High-risk actions
    if any(kw in action for kw in ["denied", "deny", "block", "intrusion", "brute", "scan", "exfiltration", "malware"]):
        score += 25
    elif any(kw in action for kw in ["failed", "error", "unauthorized"]):
        score += 15
    elif any(kw in action for kw in ["login", "access", "changed", "modified"]):
        score += 5

    score = min(score, 100)

    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 40:
        level = "MEDIUM"
    else:
        level = "LOW"

    return score, level


def normalize_parsed_data(parsed: dict, format_type: str, raw_log: str) -> dict:
    """Convert parsed fields into ECS-like canonical structure."""
    event_data = {}
    source_ip = None
    source_port = None
    dest_ip = None
    dest_port = None
    network_protocol = None
    user_name = None
    device_vendor = None
    device_product = None
    message = None

    if format_type == "CEF":
        header = parsed.get("header", {})
        fields = parsed.get("fields", {})
        device_vendor = header.get("vendor")
        device_product = header.get("product")
        event_data = {
            "category": "network",
            "type": "connection",
            "action": header.get("name", "unknown"),
            "severity": header.get("severity", "unknown"),
            "outcome": "unknown"
        }
        source_ip = fields.get("src", fields.get("sourceAddress"))
        dest_ip = fields.get("dst", fields.get("destinationAddress"))
        try:
            source_port = int(fields.get("spt", 0)) or None
            dest_port = int(fields.get("dpt", 0)) or None
        except (ValueError, TypeError):
            pass
        network_protocol = fields.get("proto")
        message = fields.get("msg")

    elif format_type == "Syslog":
        event_data = {
            "category": "system",
            "type": "info",
            "action": "log",
            "severity": "info",
            "outcome": "success"
        }
        message = parsed.get("message", raw_log)
        # Try to extract IPs from message
        ip_matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', message or "")
        if ip_matches:
            source_ip = ip_matches[0]
            if len(ip_matches) > 1:
                dest_ip = ip_matches[1]
        # Extract action keywords
        msg_lower = (message or "").lower()
        if "denied" in msg_lower or "deny" in msg_lower or "block" in msg_lower:
            event_data["action"] = "Connection Denied"
            event_data["severity"] = "high"
            event_data["outcome"] = "failure"
        elif "accept" in msg_lower or "allow" in msg_lower:
            event_data["action"] = "Connection Allowed"
            event_data["severity"] = "info"
            event_data["outcome"] = "success"
        elif "login" in msg_lower or "auth" in msg_lower:
            event_data["action"] = "Authentication"
            event_data["category"] = "authentication"
            if "fail" in msg_lower:
                event_data["severity"] = "medium"
                event_data["outcome"] = "failure"

    elif format_type == "JSON":
        event_data = {
            "category": parsed.get("event", {}).get("category", parsed.get("category", "unknown")) if isinstance(parsed.get("event"), dict) else parsed.get("category", "unknown"),
            "type": parsed.get("event", {}).get("type", "unknown") if isinstance(parsed.get("event"), dict) else "unknown",
            "action": parsed.get("event", {}).get("action", parsed.get("action", "unknown")) if isinstance(parsed.get("event"), dict) else parsed.get("action", "unknown"),
            "severity": parsed.get("event", {}).get("severity", parsed.get("severity", "info")) if isinstance(parsed.get("event"), dict) else parsed.get("severity", "info"),
            "outcome": parsed.get("event", {}).get("outcome", "unknown") if isinstance(parsed.get("event"), dict) else "unknown",
        }
        source_ip = parsed.get("source", {}).get("ip") if isinstance(parsed.get("source"), dict) else parsed.get("src_ip", parsed.get("source_ip"))
        dest_ip = parsed.get("destination", {}).get("ip") if isinstance(parsed.get("destination"), dict) else parsed.get("dst_ip", parsed.get("dest_ip"))
        user_name = parsed.get("user", {}).get("name") if isinstance(parsed.get("user"), dict) else parsed.get("userName")
        message = parsed.get("message", parsed.get("msg"))

    else:
        # CSV, XML, LEEF, UNKNOWN
        event_data = {
            "category": "unknown",
            "type": "unknown",
            "action": "unknown",
            "severity": "info",
            "outcome": "unknown"
        }
        message = str(parsed)[:500] if parsed else raw_log[:500]

    return {
        "event_data": event_data,
        "source_ip": source_ip,
        "source_port": source_port,
        "dest_ip": dest_ip,
        "dest_port": dest_port,
        "network_protocol": network_protocol,
        "user_name": user_name,
        "device_vendor": device_vendor,
        "device_product": device_product,
        "message": message,
    }


def process_raw_event(
    db: Session,
    event_id: str,
    raw_log: str,
    source_id: str,
    raw_sha256: str,
    raw_location: str,
    parser_id: Optional[str] = None,
    parser_version: Optional[str] = None,
) -> Optional[NormalizedEvent]:
    """
    Full synchronous processing pipeline.
    Returns NormalizedEvent on success, creates DLQEvent on failure.
    """
    try:
        # 1. Detect format
        detection = detect_format(raw_log)
        format_type = detection["format"]
        detect_confidence = detection["confidence"]

        if format_type == "UNKNOWN":
            raise ValueError(f"Unknown log format (confidence={detect_confidence})")

        # 2. Parse
        parsed = parse_log(raw_log, format_type)
        if not parsed or parsed == {} or (isinstance(parsed, dict) and parsed.get("raw") == raw_log):
            raise ValueError(f"Parser returned empty result for format {format_type}")

        # 3. Normalize
        normalized = normalize_parsed_data(parsed, format_type, raw_log)

        # 4. PII Redaction
        redacted_message, redacted_fields = redact_pii(normalized.get("message") or "")
        normalized["message"] = redacted_message

        # 5. Risk Score
        risk_score, risk_level = compute_risk_score(
            normalized["event_data"],
            normalized.get("source_ip")
        )

        # 6. Quality Score
        filled = sum(1 for v in [
            normalized["source_ip"], normalized["dest_ip"],
            normalized["event_data"].get("action"), normalized["event_data"].get("severity"),
            normalized["message"], normalized.get("user_name"),
            normalized.get("network_protocol")
        ] if v and v != "unknown")
        quality_score = min(100, int(filled / 7 * 100))

        # 7. Build canonical JSON
        canonical = {
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": normalized["event_data"],
            "source": {"ip": normalized["source_ip"], "port": normalized["source_port"]},
            "destination": {"ip": normalized["dest_ip"], "port": normalized["dest_port"]},
            "network": {"protocol": normalized["network_protocol"]},
            "device": {"vendor": normalized["device_vendor"], "product": normalized["device_product"]},
            "user": {"name": normalized["user_name"]} if normalized["user_name"] else None,
            "parser": {"format": format_type, "parser_version": parser_version or "1.0.0", "parser_id": parser_id},
            "normalization": {"mapping_method": "deterministic", "confidence": detect_confidence},
            "provenance": {"raw_event_id": event_id, "raw_sha256": raw_sha256},
            "risk": {"score": risk_score, "level": risk_level},
            "message": redacted_message,
        }

        # 8. SHA-256 of normalized content
        normalized_sha256 = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()

        # 9. Create NormalizedEvent
        norm_event = NormalizedEvent(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc),
            source_id=source_id if source_id != "UNKNOWN" else None,
            event_data=normalized["event_data"],
            source_ip=normalized["source_ip"],
            source_port=normalized["source_port"],
            dest_ip=normalized["dest_ip"],
            dest_port=normalized["dest_port"],
            network_protocol=normalized["network_protocol"],
            user_name=normalized["user_name"],
            device_vendor=normalized["device_vendor"],
            device_product=normalized["device_product"],
            message=redacted_message,
            parser_id=parser_id,
            parser_version=parser_version or "1.0.0",
            parser_format=format_type,
            mapping_method="deterministic",
            normalization_confidence=detect_confidence,
            risk_score=risk_score,
            risk_level=risk_level,
            raw_sha256=raw_sha256,
            normalized_sha256=normalized_sha256,
            raw_location=raw_location,
            quality_score=quality_score,
            integrity_verified=True,
            redacted_fields=redacted_fields if redacted_fields else None,
            canonical_json=canonical,
            severity=normalized["event_data"].get("severity"),
            action=normalized["event_data"].get("action"),
        )
        db.add(norm_event)

        # 10. Audit log
        audit = AuditLog(
            user="system",
            action="event_processed",
            entity_type="NormalizedEvent",
            entity_id=event_id,
            after_state={"format": format_type, "risk_score": risk_score, "quality": quality_score},
        )
        db.add(audit)

        # Update raw metadata status
        meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == event_id).first()
        if meta:
            meta.processing_status = "normalized"

        db.commit()
        return norm_event

    except Exception as e:
        db.rollback()
        # Create DLQ entry
        dlq = DLQEvent(
            event_id=event_id,
            source_id=source_id if source_id != "UNKNOWN" else None,
            raw_log=raw_log[:2000],  # Truncate for storage
            raw_location=raw_location,
            failure_reason=type(e).__name__,
            failure_detail=str(e)[:500],
            parser_id=parser_id,
            parser_version=parser_version,
            status="failed",
        )
        db.add(dlq)

        # Update raw metadata status
        meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == event_id).first()
        if meta:
            meta.processing_status = "failed"

        audit = AuditLog(
            user="system",
            action="event_processing_failed",
            entity_type="DLQEvent",
            entity_id=event_id,
            after_state={"reason": type(e).__name__, "detail": str(e)[:200]},
        )
        db.add(audit)
        db.commit()
        return None
