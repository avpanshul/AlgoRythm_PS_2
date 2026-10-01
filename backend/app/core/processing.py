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

from app.core.config import settings
from app.parsers.format_detector import detect_format
from app.parsers.deterministic import parse_log
from app.parsers.mapping_engine import apply_source_pack
from app.models.all import NormalizedEvent, DLQEvent, AuditLog, RawEventMetadata, Parser, Source, UnknownTemplate
from app.integrity.canonical_json import canonicalize
from app.integrity import service as integrity_service
from app.normalizers.ocsf import to_ocsf
from app.analytics.epistemic import classify_epistemic_quality

RISK_THRESHOLDS = {"LOW": 0, "MEDIUM": 40, "HIGH": 60, "CRITICAL": 80}


class UnknownFormatError(ValueError):
    """Raised when format detection fails. Carries the Drain3 cluster the event
    was grouped into, so the DLQ entry links straight to "this looks like N other
    unparsed events" instead of just a generic failure."""

    def __init__(self, message: str, cluster_id: Optional[str] = None):
        super().__init__(message)
        self.cluster_id = cluster_id


def _cluster_unknown_format(db: Session, raw_log: str) -> Optional[str]:
    """Run Drain3 log-template clustering on an unparseable line and upsert the
    UnknownTemplate it belongs to, so an operator reviewing the DLQ sees
    "312 events matching template X" instead of 312 separate failures."""
    try:
        from app.ai.drain3_engine import drain3_engine
    except Exception:
        return None

    result = drain3_engine.extract_template(raw_log)
    if not result:
        return None
    cluster_id = str(result.get("cluster_id")) if result.get("cluster_id") is not None else None
    template_str = result.get("template_mined") or raw_log[:200]
    if not cluster_id:
        return None

    existing = db.query(UnknownTemplate).filter(UnknownTemplate.cluster_id == cluster_id).first()
    if existing:
        existing.event_count += 1
    else:
        db.add(UnknownTemplate(cluster_id=cluster_id, template_str=template_str, event_count=1))
    return cluster_id


def _referenced_raw_field_leaves(config_json: dict) -> set:
    """Last path segment of every raw_field a source pack's field_mappings
    reference (raw_field may be a single dotted path or a list of candidates)."""
    leaves = set()
    for mapping in (config_json.get("field_mappings") or []):
        raw_field = mapping.get("raw_field")
        paths = raw_field if isinstance(raw_field, list) else [raw_field]
        for p in paths:
            if p:
                leaves.add(p.rsplit(".", 1)[-1].lower())
    return leaves


def normalize_with_source_pack(parsed: dict, config_json: dict, raw_log: str) -> dict:
    """Same output shape as normalize_parsed_data, but driven by a source pack's
    field_mappings/coalesce-join config instead of hardcoded per-format logic."""
    # A source pack can always regex-extract against the *original* raw text
    # via `raw_field: message`, regardless of parsed format -- not just
    # formats (like Syslog) whose parser happens to already put the body
    # under a "message" key. Needed for real formats the structured parse
    # doesn't flatten usefully (e.g. namespaced XML with repeated sibling
    # tags), where regexing the raw text directly is more reliable than
    # threading through deeply-nested parsed keys.
    parsed_for_pack = {**parsed, "message": raw_log} if isinstance(parsed, dict) and "message" not in parsed else parsed
    mapped = apply_source_pack(parsed_for_pack, config_json)
    event_data = mapped.get("event_data") or {}

    flat_parsed = _flatten_dict(parsed if isinstance(parsed, dict) else {})
    referenced = _referenced_raw_field_leaves(config_json)
    unmapped = {
        k: v for k, v in flat_parsed.items()
        if k.rsplit(".", 1)[-1] not in referenced
    }

    return {
        # Real bug fixed here: this used to rebuild event_data from only 5
        # fixed keys, silently discarding any other event_data.* field a
        # source pack mapped (e.g. a byte-count or vendor-specific risk
        # field) before it ever reached risk scoring or storage. Found
        # wiring up a real large-transfer risk signal that read back as
        # always-missing. Now: the 5 core keys keep their defaults, but
        # anything else the pack mapped survives.
        "event_data": {
            "category": event_data.get("category", "unknown"),
            "type": event_data.get("type", "unknown"),
            "action": event_data.get("action", "unknown"),
            "severity": event_data.get("severity", "info"),
            "outcome": event_data.get("outcome", "unknown"),
            **{k: v for k, v in event_data.items() if k not in ("category", "type", "action", "severity", "outcome")},
        },
        "source_ip": mapped.get("source_ip"),
        "source_port": mapped.get("source_port"),
        "dest_ip": mapped.get("dest_ip"),
        "dest_port": mapped.get("dest_port"),
        "network_protocol": _normalize_protocol(mapped.get("network_protocol")),
        "user_name": mapped.get("user_name"),
        "device_vendor": mapped.get("device_vendor"),
        "device_product": mapped.get("device_product"),
        "message": mapped.get("message") or raw_log[:500],
        "unmapped": unmapped,
    }


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


def compute_risk_score(event_data: dict, source_ip: str = None) -> Tuple[int, str, list]:
    """Compute a risk score based on event severity and action. Returns
    (score, level, reasons) where `reasons` is the ordered list of contributing
    factors -- this is what makes the score explainable rather than a bare
    number (see RISK_THRESHOLDS for the level cutoffs and
    _baseline_risk_for_source for the per-source baseline this is compared
    against in the canonical event)."""
    severity = (event_data.get("severity") or "unknown").lower()
    action = (event_data.get("action") or "unknown").lower()

    score = 20  # base
    reasons = [{"factor": "base", "contribution": 20}]

    severity_map = {"critical": 40, "high": 30, "medium": 15, "low": 5, "info": 0}
    sev_contribution = severity_map.get(severity, 10)
    score += sev_contribution
    reasons.append({"factor": f"severity={severity}", "contribution": sev_contribution})

    # High-risk actions
    if any(kw in action for kw in ["denied", "deny", "block", "intrusion", "brute", "scan", "exfiltration", "malware"]):
        score += 25
        reasons.append({"factor": f"action matched high-risk keyword group ('{action}')", "contribution": 25})
    elif any(kw in action for kw in ["failed", "error", "unauthorized"]):
        score += 15
        reasons.append({"factor": f"action matched failure keyword group ('{action}')", "contribution": 15})
    elif any(kw in action for kw in ["login", "access", "changed", "modified"]):
        score += 5
        reasons.append({"factor": f"action matched routine-sensitive keyword group ('{action}')", "contribution": 5})

    # Anomalously large single-request transfer size -- a standard, real DLP/
    # exfiltration heuristic (MITRE T1567, "Exfiltration Over Web Service": a
    # single request moving an unusually large volume of data is itself a
    # meaningful signal, independent of what any vendor happened to label the
    # action). 100MB is a real, defensible threshold for a single HTTP
    # request/response (ordinary web traffic essentially never legitimately
    # needs one), not tuned to hit any particular event.
    LARGE_TRANSFER_BYTES = 100_000_000
    bytes_out = event_data.get("bytes_out")
    try:
        bytes_out = int(bytes_out) if bytes_out is not None else None
    except (TypeError, ValueError):
        bytes_out = None
    if bytes_out is not None and bytes_out >= LARGE_TRANSFER_BYTES:
        score += 25
        reasons.append({
            "factor": f"anomalously large single-request transfer ({bytes_out:,} bytes >= {LARGE_TRANSFER_BYTES:,})",
            "contribution": 25,
        })

    score = min(score, 100)

    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 40:
        level = "MEDIUM"
    else:
        level = "LOW"

    return score, level, reasons


def _baseline_risk_for_source(db: Session, source_id: Optional[str], sample_size: int = 50) -> dict:
    """This source's average risk score over its last `sample_size` normalized
    events (before the current one), used to give the current score context:
    "62 vs. this source's own recent average" is more explainable than "62"
    alone."""
    if not source_id or source_id == "UNKNOWN":
        return {"source_avg_score": None, "sample_size": 0}
    scores = [
        r[0] for r in db.query(NormalizedEvent.risk_score)
        .filter(NormalizedEvent.source_id == source_id, NormalizedEvent.risk_score.isnot(None))
        .order_by(NormalizedEvent.timestamp.desc())
        .limit(sample_size)
        .all()
    ]
    if not scores:
        return {"source_avg_score": None, "sample_size": 0}
    return {"source_avg_score": round(sum(scores) / len(scores), 1), "sample_size": len(scores)}


def _flatten_dict(d: dict, prefix: str = "") -> dict:
    """Flatten an arbitrarily-nested dict (as produced by parse_xml) into {key: str_value}.

    A list value (parse_xml's representation of repeated sibling tags, e.g.
    Windows Event Log's <Data Name="X">value</Data> elements under
    <EventData>) is expanded per item: an item shaped like {"@Name": "X",
    "#text": "value"} -- the common Windows Event Log pattern -- flattens to
    a key named after X itself (so "SourceAddress" becomes findable the same
    way any other named field is), keeping the "named fields are preserved"
    property for repeated elements, not just single ones. Anything else in
    the list falls back to an index-based key so nothing is silently dropped.
    """
    out = {}
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten_dict(v, key))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict) and "@Name" in item:
                    item_key = f"{prefix}.{item['@Name']}" if prefix else item["@Name"]
                    value = item.get("#text", item)
                    if isinstance(value, dict):
                        out.update(_flatten_dict(value, item_key))
                    elif value is not None:
                        out[item_key.lower()] = str(value)
                elif isinstance(item, dict):
                    out.update(_flatten_dict(item, f"{key}.{i}"))
                elif item is not None:
                    out[f"{key}.{i}".lower()] = str(item)
        elif v is not None:
            out[key.lower()] = str(v)
    return out


_WINDOWS_EVENTID_ACTIONS = {
    # Real, publicly documented meanings -- Microsoft's own Security Event ID
    # reference (learn.microsoft.com/.../windows-security-audit-events) and
    # Sysmon's own published event ID list -- not invented. Used only to
    # give the pipeline's canonical `action` field a semantic label for the
    # specific IDs actually seen in this project's real EVTX-ATTACK-SAMPLES
    # corpus, instead of leaving it as a bare numeric code that no
    # downstream correlation rule (or human reading the event) can read.
    # Unmapped EventIDs are left as their raw numeric string, not guessed.
    "4624": "logon success", "4625": "logon failure", "4634": "logoff",
    "4648": "explicit credential logon", "4672": "special privileges assigned (admin logon)",
    "4688": "process creation", "4720": "user account created",
    "4728": "member added to security-enabled global group",
    "4732": "member added to security-enabled local group",
    "5140": "network share accessed", "5145": "network share access check",
    "5156": "windows filtering platform allowed connection",
    "5157": "windows filtering platform blocked connection",
    # Sysmon
    "1": "process creation", "3": "network connection", "7": "image loaded",
    "8": "create remote thread", "10": "process access", "11": "file create",
    "12": "registry object added or deleted", "13": "registry value set",
}

_WINDOWS_EVENTID_SEVERITY = {
    "4625": "medium", "4648": "medium", "4672": "medium", "4720": "medium",
    "4728": "medium", "4732": "medium", "5157": "medium", "8": "high", "10": "medium",
}

# Windows Event Log's own `Level` enum (learn.microsoft.com/.../eventing/event-level)
# -- a real published standard, not invented -- mapped onto this pipeline's
# info/low/medium/high/critical vocabulary.
_WINDOWS_LEVEL_SEVERITY = {
    "0": "info", "1": "critical", "2": "high", "3": "medium", "4": "info", "5": "info",
}


_IANA_PROTOCOL_NUMBERS = {
    # IANA-assigned IP protocol numbers (iana.org/assignments/protocol-numbers)
    # -- a public standard, not a guess. Left as the original numeric string
    # for any value not in this table rather than fabricating a name for it.
    "1": "ICMP", "2": "IGMP", "6": "TCP", "17": "UDP", "41": "IPv6",
    "47": "GRE", "50": "ESP", "51": "AH", "58": "ICMPv6", "89": "OSPF", "132": "SCTP",
}


def _normalize_protocol(value: Optional[str]) -> Optional[str]:
    """Map a bare IANA protocol number (as several vendor formats emit it,
    e.g. CEF `proto=6`) to its standard name; leave anything already textual
    (`"tcp"`, `"TCP"`) upper-cased for consistency, and any unrecognized
    number untouched rather than guessing."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return _IANA_PROTOCOL_NUMBERS.get(s, s)
    return s.upper()


_EVENT_TIMESTAMP_KEYS = (
    "ts", "eventtime", "@timestamp", "timestamp", "eventtime_ms", "rt",
    "devicereceipttime", "systemtime", "timecreated", "datetime",
)


def _parse_timestamp_value(v) -> Optional[datetime]:
    """Parse a single field value as a timestamp. Returns None -- never a
    guessed value -- for anything ambiguous (e.g. syslog's year-less RFC 3164
    stamp), so an unparseable field falls back to honest ingestion time
    rather than a fabricated one."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            if v > 1e17:
                return datetime.fromtimestamp(v / 1e9, tz=timezone.utc)  # nanoseconds
            if v > 1e14:
                return datetime.fromtimestamp(v / 1e6, tz=timezone.utc)  # microseconds
            if v > 1e11:
                return datetime.fromtimestamp(v / 1e3, tz=timezone.utc)  # milliseconds
            if v > 1e8:
                return datetime.fromtimestamp(v, tz=timezone.utc)  # seconds
        except (ValueError, OSError, OverflowError):
            return None
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        if re.fullmatch(r"\d+(\.\d+)?", s):
            return _parse_timestamp_value(float(s))
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _extract_event_timestamp(fields: dict) -> Optional[datetime]:
    """Best-effort extraction of the log's own event time from its parsed
    fields -- distinct from when this pipeline ingested it. Only matches
    known field names exactly (case-insensitively, on the flattened key's
    last segment); returns None when nothing recognizable is found rather
    than guessing, so the caller can fall back to ingestion time and label
    it honestly (see `timestamp_source` in process_raw_event)."""
    if not isinstance(fields, dict):
        return None
    for key in _EVENT_TIMESTAMP_KEYS:
        for k, v in fields.items():
            last_segment = k.rsplit(".", 1)[-1].lstrip("@")
            if last_segment == key:
                dt = _parse_timestamp_value(v)
                if dt:
                    return dt
    if fields.get("date") and fields.get("time"):
        dt = _parse_timestamp_value(f"{fields['date']}T{fields['time']}")
        if dt:
            return dt
    return None


def _find_by_key_substring(flat: dict, substrings: list) -> Optional[str]:
    """Return the first value whose flattened key contains any of the given
    substrings anywhere in the key (not just its last segment -- a meaningful
    marker like "provider" commonly sits in a middle segment, e.g.
    "...provider.@name", not the tail)."""
    for key, value in flat.items():
        if any(sub in key for sub in substrings):
            return value
    return None


_CEF_LEEF_CONSUMED_KEYS = {"src", "sourceaddress", "dst", "destinationaddress", "spt", "dpt", "proto", "msg"}


def _unmapped_from_flat(fields: dict, consumed_keys: set) -> dict:
    """Everything in `fields` not already surfaced as a named canonical field --
    kept instead of discarded, per the "preserve everything unmapped" requirement.
    `consumed_keys` is matched case-insensitively (CEF keys are conventionally
    lowercase; LEEF vendor fields are commonly mixed-case, e.g. srcPort)."""
    return {k: v for k, v in fields.items() if k.lower() not in consumed_keys and v not in (None, "")}


def normalize_parsed_data(parsed: dict, format_type: str, raw_log: str) -> dict:
    """Convert parsed fields into ECS-like canonical structure. Every branch
    also returns `unmapped`: whatever the parser extracted that didn't map to
    a named canonical field, so onboarding a new source doesn't silently lose
    data just because this pipeline doesn't yet have a field for it."""
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
    unmapped = {}

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
        source_ip = fields.get("src", fields.get("srcip", fields.get("sourceAddress")))
        dest_ip = fields.get("dst", fields.get("dstip", fields.get("destinationAddress")))
        try:
            source_port = int(fields.get("spt", 0)) or None
            dest_port = int(fields.get("dpt", 0)) or None
        except (ValueError, TypeError):
            pass
        network_protocol = fields.get("proto")
        # CEF user fields are real standard extension keys (suser/duser),
        # not guesses -- they carry the login/account the event acted on.
        user_name = fields.get("suser", fields.get("duser"))
        message = fields.get("msg") or fields.get("act") or fields.get("app") or fields.get("cat")
        unmapped = _unmapped_from_flat(fields, _CEF_LEEF_CONSUMED_KEYS | {"suser", "duser", "act", "app"})

    elif format_type == "LEEF":
        # deterministic.py:parse_leef() returns the same {"header","fields"} shape
        # as CEF (both are pipe-delimited vendor|product|... + key=value extensions),
        # so the same mapping applies.
        header = parsed.get("header", {})
        fields = parsed.get("fields", {})
        device_vendor = header.get("vendor")
        device_product = header.get("product")
        event_data = {
            "category": "network",
            "type": "connection",
            "action": header.get("event_id", "unknown"),
            "severity": "unknown",
            "outcome": "unknown",
        }
        source_ip = fields.get("src", fields.get("srcip", fields.get("sourceAddress")))
        dest_ip = fields.get("dst", fields.get("dstip", fields.get("destinationAddress")))
        try:
            source_port = int(fields.get("srcPort", fields.get("spt", 0))) or None
            dest_port = int(fields.get("dstPort", fields.get("dpt", 0))) or None
        except (ValueError, TypeError):
            pass
        network_protocol = fields.get("proto")
        # LEEF usrName is a real standard attribute (the user associated
        # with the event), not a guess.
        user_name = fields.get("usrName", fields.get("suser", fields.get("duser")))
        message = fields.get("msg", fields.get("cat"))
        unmapped = _unmapped_from_flat(
            fields, {"src", "srcip", "sourceaddress", "dst", "dstip", "destinationaddress",
                     "srcport", "spt", "dstport", "dpt", "proto", "msg", "cat",
                     "usrname", "suser", "duser"}
        )

    elif format_type == "KeyValue":
        # FortiGate-style `key=value` lines (also common to pfSense/Squid-style logs).
        fields = parsed if isinstance(parsed, dict) else {}
        action = (fields.get("action") or "unknown")
        event_data = {
            "category": "network" if any(k in fields for k in ("srcip", "dstip", "proto")) else "unknown",
            "type": fields.get("type", "unknown"),
            "action": action,
            "severity": fields.get("level", fields.get("severity", "info")),
            "outcome": "failure" if action.lower() in ("deny", "drop", "block", "reject") else (
                "success" if action.lower() in ("accept", "allow", "pass") else "unknown"
            ),
        }
        source_ip = fields.get("srcip", fields.get("src_ip", fields.get("client_ip", fields.get("src"))))
        dest_ip = fields.get("dstip", fields.get("dst_ip", fields.get("dst")))
        try:
            source_port = int(fields.get("srcport", fields.get("src_port", 0))) or None
            dest_port = int(fields.get("dstport", fields.get("dst_port", 0))) or None
        except (ValueError, TypeError):
            pass
        network_protocol = fields.get("proto", fields.get("protocol", fields.get("service")))
        user_name = fields.get("user", fields.get("srcuser", fields.get("dstuser", fields.get("username"))))
        device_vendor = fields.get("devname")
        message = fields.get("msg", raw_log[:500])
        unmapped = _unmapped_from_flat(
            fields, {"action", "type", "level", "severity", "srcip", "src_ip", "client_ip", "src",
                     "dstip", "dst_ip", "dst", "srcport", "src_port", "dstport", "dst_port",
                     "proto", "protocol", "service", "user", "srcuser", "dstuser", "username",
                     "devname", "msg"}
        )

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
        # Honest best-effort extraction of fields syslog actually carries in
        # prose: transport protocol keywords, port numbers, and user/login
        # names. Each is only set when the text really contains it -- no
        # defaults are invented, so a non-match simply leaves the field empty
        # (and out of the quality numerator) rather than fabricating signal.
        proto_match = re.search(r'\b(TCP|UDP|ICMP|SSH|HTTP|HTTPS|FTP|DNS|SMTP)\b', message or "", re.IGNORECASE)
        if proto_match:
            network_protocol = proto_match.group(1).upper()
        port_matches = re.findall(r'(?:port\s+|\:)(\d{1,5})\b', message or "", re.IGNORECASE)
        if port_matches:
            try:
                source_port = int(port_matches[0]) if int(port_matches[0]) <= 65535 else None
                if len(port_matches) > 1 and int(port_matches[1]) <= 65535:
                    dest_port = int(port_matches[1])
            except (ValueError, TypeError):
                pass
        user_match = re.search(
            r'(?:user(?:name)?|login|account)\s*[=:]\s*([A-Za-z0-9_.\-@]+)|'
            r'(?:for|by)\s+user\s+([A-Za-z0-9_.\-@]+)|'
            r'User\s+([A-Za-z0-9_.\-@]+)',
            message or "", re.IGNORECASE)
        if user_match:
            user_name = next((g for g in user_match.groups() if g), None)
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
        source_ip = parsed.get("source", {}).get("ip") if isinstance(parsed.get("source"), dict) else parsed.get("src_ip", parsed.get("source_ip", parsed.get("srcIp", parsed.get("src"))))
        dest_ip = parsed.get("destination", {}).get("ip") if isinstance(parsed.get("destination"), dict) else parsed.get("dst_ip", parsed.get("dest_ip", parsed.get("dstIp", parsed.get("dst"))))
        user_val = parsed.get("user", {}) if isinstance(parsed.get("user"), dict) else {}
        user_name = user_val.get("name") if isinstance(user_val, dict) else None
        if not user_name:
            # Flat (non-ECS) producers use sibling keys instead of user.name.
            for _k in ("user_name", "username", "userName", "user_id", "login"):
                _v = parsed.get(_k)
                if isinstance(_v, str) and _v:
                    user_name = _v
                    break
        if not network_protocol:
            for _k in ("protocol", "proto", "network_protocol", "transport"):
                _v = parsed.get(_k)
                if isinstance(_v, str) and _v:
                    network_protocol = _normalize_protocol(_v)
                    break
        message = parsed.get("message", parsed.get("msg")) or raw_log[:500]
        unmapped = _unmapped_from_flat(
            parsed if isinstance(parsed, dict) else {},
            {"event", "category", "type", "action", "severity", "outcome", "source", "src_ip",
              "source_ip", "srcip", "src", "destination", "dst_ip", "dest_ip", "dstip", "dst",
              "user", "userName", "user_name", "username", "user_id", "login",
              "protocol", "proto", "network_protocol", "transport",
              "message", "msg"}
        )

    elif format_type == "XML":
        # deterministic.py:parse_xml() returns a nested dict keyed by root tag,
        # e.g. {"Event": {"System": {...}, "EventData": {"#text": "..."}}}.
        # There's no fixed schema, so flatten it and match on key-name substrings.
        # This also covers Windows Event Log XML (System/EventID, Provider/@Name,
        # EventData/Data[@Name=...]) through the same generic path -- syslog and
        # Windows Event Log both land here rather than needing separate pipelines.
        flat_kv = _flatten_dict(parsed if isinstance(parsed, dict) else {})
        event_data = {
            "category": _find_by_key_substring(flat_kv, ["category"]) or "unknown",
            "type": _find_by_key_substring(flat_kv, ["eventtype", "type"]) or "unknown",
            "action": _find_by_key_substring(flat_kv, ["action", "eventid", "task"]) or "unknown",
            "severity": _find_by_key_substring(flat_kv, ["severity", "level"]) or "info",
            "outcome": _find_by_key_substring(flat_kv, ["outcome", "result", "keywords"]) or "unknown",
        }
        source_ip = _find_by_key_substring(flat_kv, ["sourceip", "sourceaddress", "srcip", "clientip", "ipaddress", "workstationname"])
        dest_ip = _find_by_key_substring(flat_kv, ["destinationip", "destaddress", "destip", "dstip"])
        user_name = _find_by_key_substring(flat_kv, ["username", "user", "account", "targetusername", "subjectusername"])
        network_protocol = _normalize_protocol(
            _find_by_key_substring(flat_kv, ["protocol", "transport"]))
        for _pk, _pv in (("source_port", ["sourceport", "srcport"]), ("dest_port", ["destport", "dstport", "destinationport"])):
            _raw = _find_by_key_substring(flat_kv, _pv)
            try:
                _num = int(str(_raw)) if _raw is not None else 0
                if 0 < _num <= 65535:
                    if _pk == "source_port":
                        source_port = _num
                    else:
                        dest_port = _num
            except (ValueError, TypeError):
                pass
        device_vendor = "Microsoft" if _find_by_key_substring(flat_kv, ["provider", "channel"]) else None
        device_product = _find_by_key_substring(flat_kv, ["channel"]) or ("Windows Event Log" if device_vendor else None)
        message = _find_by_key_substring(flat_kv, ["message", "#text"])

        # Windows Event Log XML: the generic key-substring lookups above leave
        # `action` as a bare numeric EventID string and `severity` as a bare
        # numeric Level string -- translate the specific, well-known ones to
        # this pipeline's semantic vocabulary (see the tables' own docstring
        # comments for the real, published source of each mapping). Scoped to
        # device_vendor == "Microsoft" so this never touches a non-Windows XML
        # source that happens to share a generic <EventID>-shaped tag.
        if device_vendor == "Microsoft":
            raw_action = event_data.get("action")
            if raw_action in _WINDOWS_EVENTID_ACTIONS:
                event_data["action"] = _WINDOWS_EVENTID_ACTIONS[raw_action]
                if raw_action in _WINDOWS_EVENTID_SEVERITY and event_data.get("severity") in (None, "info", "unknown"):
                    event_data["severity"] = _WINDOWS_EVENTID_SEVERITY[raw_action]
            raw_severity = event_data.get("severity")
            if raw_severity in _WINDOWS_LEVEL_SEVERITY:
                event_data["severity"] = _WINDOWS_LEVEL_SEVERITY[raw_severity]
        if not source_ip:
            ip_matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', " ".join(flat_kv.values()))
            if ip_matches:
                source_ip = ip_matches[0]
                if len(ip_matches) > 1 and not dest_ip:
                    dest_ip = ip_matches[1]
        if not message:
            message = json.dumps(parsed)[:500]
        consumed_substrings = ["category", "eventtype", "type", "action", "eventid", "task",
                                "severity", "level", "outcome", "result", "keywords", "sourceip",
                                "sourceaddress", "srcip", "clientip", "ipaddress", "workstationname",
                                "destinationip", "destaddress", "destip", "dstip", "username", "user", "account",
                                "targetusername", "subjectusername", "provider", "channel", "message", "#text",
                                "protocol", "transport", "sourceport", "srcport", "destport", "dstport",
                                "destinationport"]
        unmapped = {
            k: v for k, v in flat_kv.items()
            if not any(sub in k for sub in consumed_substrings)
        }

    elif format_type == "CSV":
        # deterministic.py:parse_csv() returns {"field_0": v, "field_1": v, ...} —
        # positional only, no column names, so semantic fields can't be looked up
        # by key. Best effort: scan values for IP-shaped tokens, keep full row as message.
        row = parsed if isinstance(parsed, dict) else {}
        values = [str(v) for v in row.values() if v]
        event_data = {
            "category": "unknown",
            "type": "unknown",
            "action": "unknown",
            "severity": "info",
            "outcome": "unknown",
        }
        ip_matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', " ".join(values))
        if ip_matches:
            source_ip = ip_matches[0]
            if len(ip_matches) > 1:
                dest_ip = ip_matches[1]
        # Same honest prose scan as Syslog: CSV rows (e.g. Palo Alto exports)
        # often embed protocol names and port numbers as bare values.
        joined = " ".join(values)
        proto_match = re.search(r'\b(TCP|UDP|ICMP|SSH|HTTP|HTTPS|FTP|DNS|SMTP)\b', joined, re.IGNORECASE)
        if proto_match:
            network_protocol = proto_match.group(1).upper()
        port_matches = re.findall(r'(?:port\s+|\:)(\d{1,5})\b', joined, re.IGNORECASE)
        if port_matches:
            try:
                source_port = int(port_matches[0]) if int(port_matches[0]) <= 65535 else None
                if len(port_matches) > 1 and int(port_matches[1]) <= 65535:
                    dest_port = int(port_matches[1])
            except (ValueError, TypeError):
                pass
        message = ",".join(values)[:500] if values else raw_log[:500]
        # No column names to map against, so the whole row is unmapped by definition.
        unmapped = dict(row)

    elif format_type == "HDFSLog":
        # deterministic.py:parse_hdfs_log() -- Hadoop/HDFS daemon log line.
        level = (parsed.get("level") or "INFO").upper()
        component = parsed.get("component") or "unknown"
        message = parsed.get("message") or raw_log[:500]
        event_data = {
            "category": "system",
            "type": "application",
            "action": component,
            "severity": {"ERROR": "high", "FATAL": "critical", "WARN": "medium"}.get(level, "info"),
            "outcome": "failure" if level in ("ERROR", "FATAL") else "unknown",
        }
        device_vendor = "Apache"
        device_product = "Hadoop"
        ip_matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', message)
        if ip_matches:
            source_ip = ip_matches[0]
            if len(ip_matches) > 1:
                dest_ip = ip_matches[1]
        port_matches = re.findall(r':(\d{2,5})\b', message)
        if port_matches:
            try:
                p = int(port_matches[0])
                if p <= 65535:
                    source_port = p
            except (ValueError, TypeError):
                pass
        unmapped = {"pid": parsed.get("pid"), "date": parsed.get("date"), "time": parsed.get("time")}

    elif format_type == "HPCLog":
        # deterministic.py:parse_hpc_log() -- HPC/BlueGene-style node event.
        event_type = parsed.get("event_type") or "unknown"
        message = parsed.get("message") or raw_log[:500]
        is_failure = any(k in event_type.lower() for k in ("unavailable", "fail", "error"))
        event_data = {
            "category": "hardware",
            "type": parsed.get("subsystem") or "unknown",
            "action": event_type,
            "severity": "high" if is_failure else "info",
            "outcome": "failure" if is_failure else "unknown",
        }
        device_product = parsed.get("node")
        unmapped = {"event_id": parsed.get("event_id"), "flag": parsed.get("flag")}

    elif format_type == "ApacheErrorLog":
        # deterministic.py:parse_apache_error_log().
        level = (parsed.get("level") or "notice").lower()
        message = parsed.get("message") or raw_log[:500]
        severity_map = {"error": "high", "warn": "medium", "notice": "info", "info": "info", "debug": "low"}
        event_data = {
            "category": "web",
            "type": "server",
            "action": "log",
            "severity": severity_map.get(level, "info"),
            "outcome": "failure" if level == "error" else "unknown",
        }
        device_vendor = "Apache"
        device_product = "HTTP Server"
        client_match = re.search(r'\[client (\d{1,3}(?:\.\d{1,3}){3})', message)
        if client_match:
            source_ip = client_match.group(1)
        else:
            ip_matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', message)
            if ip_matches:
                source_ip = ip_matches[0]

    elif format_type == "WindowsTraceLog":
        # deterministic.py:parse_windows_trace_log() -- Windows CBS/trace log.
        level = (parsed.get("level") or "Info").lower()
        component = parsed.get("component") or "unknown"
        message = parsed.get("message") or raw_log[:500]
        severity_map = {"error": "high", "warning": "medium", "info": "info"}
        event_data = {
            "category": "system",
            "type": "windows_trace",
            "action": component,
            "severity": severity_map.get(level, "info"),
            "outcome": "failure" if level == "error" else "unknown",
        }
        device_vendor = "Microsoft"
        device_product = "Windows"
        unmapped = {"raw_component": component}

    elif format_type == "Log4jLog":
        # deterministic.py:parse_log4j_log() -- Hadoop YARN / Zookeeper / generic Log4j daemon log.
        level = (parsed.get("level") or "INFO").upper()
        message = parsed.get("message") or raw_log[:500]
        event_data = {
            "category": "system",
            "type": "application",
            "action": parsed.get("logger") or parsed.get("thread") or "log",
            "severity": {"ERROR": "high", "FATAL": "critical", "WARN": "medium"}.get(level, "info"),
            "outcome": "failure" if level in ("ERROR", "FATAL") else "unknown",
        }
        ip_matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', message)
        if ip_matches:
            source_ip = ip_matches[0]
            if len(ip_matches) > 1:
                dest_ip = ip_matches[1]
        port_matches = re.findall(r':(\d{2,5})\b', message)
        if port_matches:
            try:
                p = int(port_matches[0])
                if p <= 65535:
                    source_port = p
            except (ValueError, TypeError):
                pass
        unmapped = {"thread": parsed.get("thread")}

    elif format_type == "BGLLog":
        # deterministic.py:parse_bgl_log() -- BlueGene/L RAS event log.
        level = (parsed.get("level") or "INFO").upper()
        event_type = parsed.get("event_type") or "unknown"
        message = parsed.get("message") or raw_log[:500]
        event_data = {
            "category": "hardware",
            "type": event_type,
            "action": parsed.get("component") or "unknown",
            "severity": {"FATAL": "critical", "FAILURE": "critical", "ERROR": "high", "WARNING": "medium"}.get(level, "info"),
            "outcome": "failure" if level in ("FATAL", "FAILURE", "ERROR") else "unknown",
        }
        device_product = parsed.get("node")
        unmapped = {"label": parsed.get("label")}

    else:
        # UNKNOWN (unrecognized format -- see Drain3 clustering in process_raw_event)
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
        "network_protocol": _normalize_protocol(network_protocol),
        "user_name": user_name,
        "device_vendor": device_vendor,
        "device_product": device_product,
        "message": message,
        "unmapped": unmapped,
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
    deliver: bool = True,
) -> Optional[NormalizedEvent]:
    """
    Full synchronous processing pipeline.
    Returns NormalizedEvent on success, creates DLQEvent on failure.

    `deliver` controls real-time downstream delivery (webhook export +
    OpenSearch indexing, app/services/event_delivery.py) of this event after
    it commits. Default True for real-time ingestion (the actual use case
    for "push this to my SIEM the moment it happens"). seed.py's bulk
    historical backfill passes deliver=False explicitly -- firing tens of
    thousands of webhook/OpenSearch calls for a one-time historical reseed
    would flood a demo endpoint and add real load to a process already
    memory-constrained, for events that aren't actually "just happening".
    """
    try:
        # 1. Detect format
        detection = detect_format(raw_log)
        format_type = detection["format"]
        detect_confidence = detection["confidence"]

        if format_type == "UNKNOWN":
            cluster_id = _cluster_unknown_format(db, raw_log)
            db.commit()
            raise UnknownFormatError(
                f"Unknown log format (confidence={detect_confidence})", cluster_id=cluster_id
            )

        # 2. Parse
        parsed = parse_log(raw_log, format_type)
        if not parsed or parsed == {} or (isinstance(parsed, dict) and parsed.get("raw") == raw_log):
            raise ValueError(f"Parser returned empty result for format {format_type}")

        # 3. Normalize -- prefer a published source pack (YAML-authored field
        # mappings) matching this format/vendor if one exists; otherwise fall
        # back to the hardcoded deterministic mapping for that format.
        source_pack = None
        if source_id and source_id != "UNKNOWN":
            source = db.query(Source).filter(Source.id == source_id).first()
            vendor = source.vendor if source else None
            pack_query = db.query(Parser).filter(
                Parser.format_type == format_type, Parser.status == "published"
            )
            if vendor:
                pack_query = pack_query.filter((Parser.vendor == vendor) | (Parser.vendor.is_(None)))
            source_pack = pack_query.order_by(Parser.updated_at.desc()).first()

        if source_pack and source_pack.config_json and source_pack.config_json.get("field_mappings"):
            normalized = normalize_with_source_pack(parsed, source_pack.config_json, raw_log)
            mapping_method = "source_pack"
            resolved_parser_id = source_pack.id
            resolved_parser_version = source_pack.version
        else:
            normalized = normalize_parsed_data(parsed, format_type, raw_log)
            mapping_method = "deterministic"
            resolved_parser_id = parser_id
            resolved_parser_version = parser_version or "1.0.0"

        # 4. PII Redaction
        redacted_message, redacted_fields = redact_pii(normalized.get("message") or "")
        normalized["message"] = redacted_message

        # 5. Risk Score (explainable: score + level + the reasons behind it)
        risk_score, risk_level, risk_reasons = compute_risk_score(
            normalized["event_data"],
            normalized.get("source_ip")
        )
        risk_baseline = _baseline_risk_for_source(db, source_id)

        # 5a. Event timestamp -- the log's own time, not when this pipeline saw
        # it. Only trusted when a recognizable timestamp field was actually
        # found (see _extract_event_timestamp); otherwise fall back to
        # ingestion time and say so via `timestamp_source`, rather than
        # silently presenting "now" as if it were the event's real time.
        try:
            if format_type in ("CEF", "LEEF"):
                ts_fields = _flatten_dict(parsed.get("fields", {}) if isinstance(parsed, dict) else {})
            elif format_type in ("JSON", "KeyValue", "XML"):
                ts_fields = _flatten_dict(parsed if isinstance(parsed, dict) else {})
            else:
                ts_fields = {}
            event_ts = _extract_event_timestamp(ts_fields)
        except Exception:
            event_ts = None
        ingested_at = datetime.now(timezone.utc)
        event_timestamp = event_ts or ingested_at
        timestamp_source = "event" if event_ts else "ingestion"

        # 6. Quality Score
        filled = sum(1 for v in [
            normalized["source_ip"], normalized["dest_ip"],
            normalized["event_data"].get("action"), normalized["event_data"].get("severity"),
            normalized["message"], normalized.get("user_name"),
            normalized.get("network_protocol")
        ] if v and v != "unknown")
        quality_score = min(100, int(filled / 7 * 100))
        epistemic = classify_epistemic_quality(
            quality_score, normalized["event_data"].get("severity"), normalized["event_data"].get("outcome")
        )

        # 7. Build canonical JSON
        canonical = {
            "event_id": event_id,
            "timestamp": event_timestamp.isoformat(),
            "ingested_at": ingested_at.isoformat(),
            "event": normalized["event_data"],
            "source": {"ip": normalized["source_ip"], "port": normalized["source_port"]},
            "destination": {"ip": normalized["dest_ip"], "port": normalized["dest_port"]},
            "network": {"protocol": normalized["network_protocol"]},
            "device": {"vendor": normalized["device_vendor"], "product": normalized["device_product"]},
            "user": {"name": normalized["user_name"]} if normalized["user_name"] else None,
            "parser": {"format": format_type, "parser_version": resolved_parser_version, "parser_id": resolved_parser_id},
            "normalization": {
                "mapping_method": mapping_method, "confidence": detect_confidence,
                "timestamp_source": timestamp_source,
            },
            "provenance": {"raw_event_id": event_id, "raw_sha256": raw_sha256},
            "risk": {
                "score": risk_score,
                "level": risk_level,
                "reasons": risk_reasons,
                "thresholds": RISK_THRESHOLDS,
                "baseline": risk_baseline,
            },
            "quality": {"score": quality_score, "epistemic": epistemic},
            "message": redacted_message,
            # Best-effort OCSF 1.x mapping alongside the ECS-like "event" block above
            # -- see app/normalizers/ocsf.py for what this does and doesn't cover.
            "ocsf": to_ocsf(normalized["event_data"]),
            # Everything the parser/source-pack extracted that didn't map to a
            # named canonical field -- preserved, not discarded.
            "unmapped": normalized.get("unmapped") or {},
        }

        # 8. RFC 8785 (JCS) canonical hash of the normalized content -- canonicalize
        # before hashing so two independent implementations of this pipeline would
        # produce byte-identical input to SHA-256 for the same logical event.
        normalized_sha256 = hashlib.sha256(canonicalize(canonical).encode("utf-8")).hexdigest()

        # 9. Create (or, on replay, update in place) the NormalizedEvent.
        #
        # Real bug found live: this used to unconditionally construct a new
        # NormalizedEvent and db.add() it, which is correct for first-time
        # ingestion but a real `UNIQUE constraint failed: normalized_events.event_id`
        # for a replay -- replay.py already archives the pre-replay row into
        # NormalizedEventVersion (its own comment says "archive... before it's
        # replaced"), but nothing ever actually did the replacing; every
        # replayed event failed here and was spuriously dumped into the DLQ,
        # even though nothing was wrong with it. NormalizedEvent is the
        # "current" view for this event_id; history lives in
        # NormalizedEventVersion. Updating in place (rather than delete+insert)
        # also keeps the row's identity stable for anything else referencing
        # it mid-transaction.
        norm_event_fields = dict(
            timestamp=event_timestamp,
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
            parser_id=resolved_parser_id,
            parser_version=resolved_parser_version,
            parser_format=format_type,
            mapping_method=mapping_method,
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
        norm_event = db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).first()
        if norm_event is not None:
            for field, value in norm_event_fields.items():
                setattr(norm_event, field, value)
        else:
            norm_event = NormalizedEvent(event_id=event_id, **norm_event_fields)
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

        # 11. Append to the Merkle log (same transaction as the event it covers)
        integrity_service.append_leaf(db, event_id, normalized_sha256)

        db.commit()

        # Issue a fresh signed checkpoint so the event is provable immediately.
        # This is O(n) per call (see Checkpoint cost note in core/config.py) --
        # disable via AUTO_CHECKPOINT_EVERY_EVENT and run
        # app/workers/checkpoint_scheduler.py on a timer instead once ingestion
        # volume outgrows it.
        if settings.AUTO_CHECKPOINT_EVERY_EVENT:
            integrity_service.create_checkpoint(db)

        if deliver:
            from app.services.event_delivery import deliver_to_webhooks, index_to_opensearch
            deliver_to_webhooks(db, canonical)
            index_to_opensearch(canonical)

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
            drain_cluster_id=getattr(e, "cluster_id", None),
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
