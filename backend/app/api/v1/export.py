"""Event export: JSON, CSV, OCSF JSON, CEF, syslog-forward text, and a STIX
2.1 bundle for threat indicators.

Security notes (Part D #6, log-injection / CSV-formula-injection handling):
  - CSV: any cell starting with =, +, -, @, tab or CR is prefixed with a
    single quote so spreadsheet software won't treat it as a formula
    ("CSV/formula injection").
  - CEF/syslog-forward (line-oriented text formats): any CR/LF/ANSI escape
    in a field is stripped before the field is written, so one malicious log
    message can't forge additional log lines in the exported file.
"""
import csv
import io
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse, PlainTextResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.all import NormalizedEvent, ThreatIndicator

router = APIRouter()

CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _csv_safe(value) -> str:
    s = "" if value is None else str(value)
    if s and (s[0] in CSV_FORMULA_PREFIXES or s[0] in ("\t", "\r")):
        return "'" + s
    return s


def _line_safe(value) -> str:
    """Strip characters that could forge additional lines/escape sequences
    in a line-oriented export (CEF, syslog-forward)."""
    s = "" if value is None else str(value)
    s = s.replace("\r", " ").replace("\n", " ")
    s = _ANSI_ESCAPE_RE.sub("", s)
    return s


def _query_events(db: Session, source_id: Optional[str], severity: Optional[str], limit: int, risk_level: Optional[str] = None,
                 q: Optional[str] = None, since_hours: Optional[float] = None):
    qy = db.query(NormalizedEvent)
    if source_id:
        qy = qy.filter(NormalizedEvent.source_id == source_id)
    if severity:
        qy = qy.filter(NormalizedEvent.severity == severity.lower())
    if risk_level:
        qy = qy.filter(NormalizedEvent.risk_level == risk_level.upper())
    if q:
        # Same honest text search as GET /events (message, IPs, action,
        # user, hash) -- previously the export endpoints silently dropped
        # the `q` param, so a filtered export returned the same file.
        qy = qy.filter(
            or_(
                NormalizedEvent.message.ilike(f"%{q}%"),
                NormalizedEvent.source_ip.ilike(f"%{q}%"),
                NormalizedEvent.dest_ip.ilike(f"%{q}%"),
                NormalizedEvent.action.ilike(f"%{q}%"),
                NormalizedEvent.user_name.ilike(f"%{q}%"),
                NormalizedEvent.raw_sha256.ilike(f"%{q}%"),
            )
        )
    if since_hours is not None:
        qy = qy.filter(NormalizedEvent.timestamp >= datetime.now(timezone.utc) - timedelta(hours=since_hours))
    return qy.order_by(NormalizedEvent.timestamp.desc()).limit(limit).all()


@router.get("/export/events.json")
def export_events_json(
    source_id: Optional[str] = None, severity: Optional[str] = None, risk_level: Optional[str] = None,
    q: Optional[str] = None, since_hours: Optional[float] = None,
    limit: int = Query(1000, ge=1, le=10000), db: Session = Depends(get_db),
):
    events = _query_events(db, source_id, severity, limit, risk_level, q, since_hours)
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(events),
        "events": [e.canonical_json for e in events if e.canonical_json],
    }
    return StreamingResponse(
        io.BytesIO(json.dumps(payload, indent=2).encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="ulpf_events.json"'},
    )


@router.get("/export/events.csv")
def export_events_csv(
    source_id: Optional[str] = None, severity: Optional[str] = None, risk_level: Optional[str] = None,
    q: Optional[str] = None, since_hours: Optional[float] = None,
    limit: int = Query(1000, ge=1, le=10000), db: Session = Depends(get_db),
):
    events = _query_events(db, source_id, severity, limit, risk_level, q, since_hours)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["event_id", "timestamp", "source_id", "source_ip", "dest_ip",
                      "action", "severity", "risk_score", "risk_level", "quality_score",
                      "parser_format", "message"])
    for e in events:
        writer.writerow([_csv_safe(v) for v in [
            e.event_id, e.timestamp.isoformat() if e.timestamp else "", e.source_id,
            e.source_ip, e.dest_ip, e.action, e.severity, e.risk_score, e.risk_level,
            e.quality_score, e.parser_format, e.message,
        ]])
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ulpf_events.csv"'},
    )


@router.get("/export/events.ocsf.json")
def export_events_ocsf(
    source_id: Optional[str] = None, severity: Optional[str] = None,
    q: Optional[str] = None, since_hours: Optional[float] = None,
    limit: int = Query(1000, ge=1, le=10000), db: Session = Depends(get_db),
):
    """Exports the `ocsf` block already embedded in each event's canonical_json
    (see app/normalizers/ocsf.py) -- best-effort mapping, not a compliance claim."""
    events = _query_events(db, source_id, severity, limit, None, q, since_hours)
    out = []
    for e in events:
        cj = e.canonical_json or {}
        ocsf = dict(cj.get("ocsf") or {})
        ocsf["event_id"] = e.event_id
        ocsf["time"] = cj.get("timestamp")
        ocsf["src_endpoint"] = {"ip": e.source_ip, "port": e.source_port}
        ocsf["dst_endpoint"] = {"ip": e.dest_ip, "port": e.dest_port}
        ocsf["message"] = e.message
        out.append(ocsf)
    payload = {"exported_at": datetime.now(timezone.utc).isoformat(), "count": len(out), "events": out}
    return StreamingResponse(
        io.BytesIO(json.dumps(payload, indent=2).encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="ulpf_events_ocsf.json"'},
    )


@router.get("/export/events.cef", response_class=PlainTextResponse)
def export_events_cef(
    source_id: Optional[str] = None, severity: Optional[str] = None,
    q: Optional[str] = None, since_hours: Optional[float] = None,
    limit: int = Query(1000, ge=1, le=10000), db: Session = Depends(get_db),
):
    events = _query_events(db, source_id, severity, limit, None, q, since_hours)
    lines = []
    for e in events:
        vendor = _line_safe(e.device_vendor or "ULPF")
        product = _line_safe(e.device_product or "ULPF")
        name = _line_safe(e.action or "event")
        severity_num = {"critical": "10", "high": "8", "medium": "5", "low": "2"}.get((e.severity or "").lower(), "0")
        ext = " ".join([
            f"src={_line_safe(e.source_ip or '')}",
            f"dst={_line_safe(e.dest_ip or '')}",
            f"spt={e.source_port or ''}",
            f"dpt={e.dest_port or ''}",
            f"proto={_line_safe(e.network_protocol or '')}",
            f"msg={_line_safe(e.message or '')}",
            f"cs1Label=RiskScore cs1={e.risk_score or ''}",
        ])
        lines.append(f"CEF:0|{vendor}|{product}|1.0|{_line_safe(e.event_id)}|{name}|{severity_num}|{ext}")
    return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""))


@router.get("/export/events.syslog", response_class=PlainTextResponse)
def export_events_syslog(
    source_id: Optional[str] = None, severity: Optional[str] = None,
    q: Optional[str] = None, since_hours: Optional[float] = None,
    limit: int = Query(1000, ge=1, le=10000), db: Session = Depends(get_db),
):
    """RFC 5424-shaped forwarding format (syslog forward)."""
    events = _query_events(db, source_id, severity, limit, None, q, since_hours)
    lines = []
    for e in events:
        ts = e.timestamp.isoformat() if e.timestamp else datetime.now(timezone.utc).isoformat()
        host = _line_safe(e.source_id or "unknown-host")
        msg = _line_safe(
            f'action="{e.action}" severity="{e.severity}" src={e.source_ip} dst={e.dest_ip} '
            f'risk={e.risk_score} msg="{e.message}"'
        )
        lines.append(f"<134>1 {ts} {host} ulpf-export - {_line_safe(e.event_id)} - {msg}")
    return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""))


@router.get("/export/indicators.stix")
def export_indicators_stix(active_only: bool = True, db: Session = Depends(get_db)):
    """Hand-built STIX 2.1 bundle (no `stix2` dependency) containing one
    Indicator object per active threat indicator."""
    q = db.query(ThreatIndicator)
    if active_only:
        q = q.filter(ThreatIndicator.active == True)  # noqa: E712
    indicators = q.all()

    stix_type_map = {"ip": "ipv4-addr", "domain": "domain-name", "hash": "file", "url": "url"}
    stix_field_map = {"ip": "value", "domain": "value", "hash": "hashes.SHA-256", "url": "value"}

    objects = []
    for ind in indicators:
        stix_obj_type = stix_type_map.get(ind.type, "artifact")
        field = stix_field_map.get(ind.type, "value")
        pattern = f"[{stix_obj_type}:{field} = '{ind.value}']"
        objects.append({
            "type": "indicator",
            "spec_version": "2.1",
            "id": f"indicator--{ind.id:08d}0000-0000-4000-8000-000000000000",
            "created": ind.created_at.isoformat() if ind.created_at else datetime.now(timezone.utc).isoformat(),
            "modified": ind.created_at.isoformat() if ind.created_at else datetime.now(timezone.utc).isoformat(),
            "name": f"{ind.threat_type or 'indicator'}: {ind.value}",
            "description": ind.description or "",
            "indicator_types": [ind.threat_type] if ind.threat_type else ["unknown"],
            "pattern": pattern,
            "pattern_type": "stix",
            "valid_from": ind.created_at.isoformat() if ind.created_at else datetime.now(timezone.utc).isoformat(),
        })

    bundle = {"type": "bundle", "id": "bundle--ulpf-export", "objects": objects}
    return StreamingResponse(
        io.BytesIO(json.dumps(bundle, indent=2).encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="ulpf_indicators.stix.json"'},
    )
