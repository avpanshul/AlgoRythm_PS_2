"""Seed script for Demo Mode (PostgreSQL-only).

Reference/config data (organizations, roles, users, sources, parsers,
correlation rules, threat intel, integrations) is hand-authored illustrative
metadata for the demo tenant -- it is not raw event content, so it is kept
here as-is.

Event data is NOT fabricated. seed_real_events() reads real, publicly
downloaded log lines from backend/datasets/real/ (see
backend/datasets/real/build_corpus.py and README notes there for
provenance: logpai/loghub raw samples -- Linux, OpenSSH, Mac, Apache,
HDFS, Hadoop, Zookeeper, Windows, HPC, BGL) and feeds every line through
the ACTUAL production pipeline (app/core/processing.py:process_raw_event),
the same code path app/api/v1/ingestion.py:process_single_log() uses for
live ingestion. parser_format, risk_score, risk_level, quality_score and
canonical_json on every seeded NormalizedEvent are therefore real pipeline
output, not hardcoded values. Lines the deterministic parser can't handle
correctly land in DLQEvent, exactly as they would in production -- that is
the pipeline's real fallback behavior, not simulated failure data.
"""
import os
import sys
import uuid
import hashlib
import json
from datetime import datetime, timezone

import yaml

# Ensure we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.core.local_storage import save_raw_log
from app.core.processing import process_raw_event
from app.models.all import (
    Base, Source, User, Role, Organization, CorrelationRule, Parser,
    ParserVersion, ThreatIndicator, Integration, PrivacyPolicy,
    NormalizedEvent, RawEventMetadata, AuditLog, DLQEvent,
)

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets", "real")
CORPUS_PATH = os.path.join(DATASET_DIR, "corpus.jsonl")


def create_db_and_tables():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)


def seed_organizations(db: Session):
    print("Seeding organizations...")
    orgs = [
        Organization(id="ORG-MEITY", name="MeitY Data Center", type="Government", sector="Technology"),
        Organization(id="ORG-CERT", name="CERT-In", type="CERT", sector="Cybersecurity"),
        Organization(id="ORG-NIC", name="National Informatics Centre", type="PSU", sector="Infrastructure"),
    ]
    for o in orgs:
        db.merge(o)
    db.commit()


def seed_roles_users(db: Session):
    print("Seeding roles and users...")
    roles = [
        Role(name="Security Admin", permissions=["all"]),
        Role(name="SOC Analyst", permissions=["read_events", "read_alerts"]),
        Role(name="Parser Developer", permissions=["write_parsers", "read_events"]),
    ]
    for r in roles:
        existing = db.query(Role).filter(Role.name == r.name).first()
        if not existing:
            db.add(r)
    db.commit()

    users = [
        User(id="U1", name="Admin User", email="admin@gov.in", role_name="Security Admin", organization_id="ORG-CERT"),
        User(id="U2", name="SOC Analyst 1", email="analyst@gov.in", role_name="SOC Analyst", organization_id="ORG-MEITY"),
        User(id="U3", name="Parser Dev", email="dev@gov.in", role_name="Parser Developer", organization_id="ORG-NIC"),
    ]
    for u in users:
        db.merge(u)
    db.commit()


def seed_sources(db: Session):
    # NOTE (labeling decision, flagged per review request): these Source rows
    # are illustrative device/config metadata for the demo tenant, not raw
    # event content -- "Palo Alto Edge" etc. are placeholder *names* for
    # sources, matching the org's placeholder naming (ORG-MEITY/CERT/NIC).
    # FW-001 and EDR-01 currently have no real event data seeded against
    # them (no public firewall/EDR raw-log corpus was pulled in this pass);
    # SYS-LNX, WEB-01, DIST-01, WIN-01 and HPC-01 do, via seed_real_events().
    print("Seeding sources...")
    sources = [
        Source(id="FW-001", name="Palo Alto Edge", vendor="Palo Alto", product="PAN-OS", device_type="Firewall", organization_id="ORG-MEITY"),
        Source(id="SYS-LNX", name="Core Linux Servers", vendor="Linux", product="Syslog", device_type="Server", organization_id="ORG-NIC"),
        Source(id="WEB-01", name="Nginx Frontends", vendor="F5", product="Nginx", device_type="Proxy", organization_id="ORG-MEITY"),
        Source(id="EDR-01", name="CrowdStrike Agents", vendor="CrowdStrike", product="Falcon", device_type="EDR", organization_id="ORG-CERT"),
        Source(id="DIST-01", name="Distributed Systems Cluster", vendor="Apache", product="Hadoop/HDFS/Zookeeper", device_type="Application", organization_id="ORG-NIC"),
        Source(id="WIN-01", name="Windows Servers", vendor="Microsoft", product="Windows Event Log", device_type="Server", organization_id="ORG-MEITY"),
        Source(id="HPC-01", name="HPC Cluster", vendor="Generic", product="HPC/BlueGene", device_type="Server", organization_id="ORG-NIC"),
    ]
    for s in sources:
        db.merge(s)
    db.commit()


def seed_parsers(db: Session):
    print("Seeding parsers...")
    nginx_yaml = """
name: Nginx Access Log Parser
vendor: F5
format: grok
pattern: '%{IPORHOST:client_ip} - %{USER:ident} \\[%{HTTPDATE:timestamp}\\] "%{WORD:method} %{URIPATHPARAM:request} HTTP/%{NUMBER:httpversion}" %{NUMBER:response} %{NUMBER:bytes}'
mappings:
  source_ip: client_ip
  action: request
"""
    parsers = [
        Parser(
            id="p-nginx", name="Nginx Access Log Parser", vendor="F5", format_type="grok",
            version="1.0.0", config_yaml=nginx_yaml, config_json=yaml.safe_load(nginx_yaml),
            status="published", created_by="admin"
        ),
        Parser(
            id="p-syslog", name="Standard Syslog", vendor="Linux", format_type="regex",
            version="2.1.0", config_yaml="name: Syslog\nformat: regex", config_json={},
            status="published", created_by="admin"
        )
    ]
    for p in parsers:
        db.merge(p)
    db.commit()


def _ensure_corpus():
    """Build datasets/real/corpus.jsonl from the downloaded loghub samples if missing."""
    if os.path.exists(CORPUS_PATH):
        return
    print(f"{CORPUS_PATH} not found, building it from backend/datasets/real/loghub/ ...")
    sys.path.insert(0, DATASET_DIR)
    import build_corpus
    build_corpus.build()


def seed_real_events(db: Session, limit: int = None):
    """
    Feed real, downloaded log lines through the actual processing pipeline
    (app.core.processing.process_raw_event) -- same code path production
    ingestion uses. Every parser_format / risk_score / quality_score /
    canonical_json value that lands in Postgres comes from that real run,
    not from this script.
    """
    _ensure_corpus()
    if not os.path.exists(CORPUS_PATH):
        print(f"WARNING: {CORPUS_PATH} still missing -- skipping real event seed.")
        return {"ok": 0, "dlq": 0, "formats": {}}

    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if limit:
        rows = rows[:limit]

    print(f"Seeding {len(rows)} real log events through the real pipeline...")

    format_counts = {}
    ok_count = 0
    dlq_count = 0

    for row in rows:
        raw_log = row["raw"]
        source_id = row.get("source_id") or "UNKNOWN"

        event_id = f"evt_{uuid.uuid4().hex}"
        raw_sha256 = hashlib.sha256(raw_log.encode("utf-8")).hexdigest()
        received_at = datetime.now(timezone.utc)
        date_path = received_at.strftime("%Y/%m/%d")
        raw_location = f"{date_path}/{event_id}.txt"

        save_raw_log(raw_location, raw_log)

        metadata = RawEventMetadata(
            event_id=event_id,
            source_id=source_id,
            received_at=received_at,
            ingestion_protocol="seed-real-loghub",
            raw_sha256=raw_sha256,
            raw_location=raw_location,
            processing_status="processing",
        )
        db.add(metadata)
        db.commit()

        norm_event = process_raw_event(db, event_id, raw_log, source_id, raw_sha256, raw_location)

        if norm_event is not None:
            ok_count += 1
            fmt = norm_event.parser_format
            format_counts[fmt] = format_counts.get(fmt, 0) + 1
        else:
            dlq_count += 1

    print(f"  -> {ok_count} NormalizedEvent rows, {dlq_count} DLQEvent rows")
    print(f"  -> format breakdown: {format_counts}")
    return {"ok": ok_count, "dlq": dlq_count, "formats": format_counts}


def seed_rules_intel_integrations(db: Session):
    print("Seeding rules, intel, and integrations...")
    rules = [
        CorrelationRule(name="Brute Force Attempt", severity="high", enabled=True, threshold=5, time_window_seconds=60, condition={"field": "action", "value": "login_failed"}),
        CorrelationRule(name="Data Exfiltration", severity="critical", enabled=True, threshold=1000000, time_window_seconds=3600, condition={"field": "bytes_out", "operator": ">"})
    ]
    for r in rules:
        db.merge(r)

    intel = [
        ThreatIndicator(type="ip", value="203.0.113.99", threat_type="C2 Server", severity="critical"),
        ThreatIndicator(type="domain", value="evil-domain.test", threat_type="Phishing", severity="high")
    ]
    for i in intel:
        db.merge(i)

    integrations = [
        Integration(name="Splunk Forwarder", type="syslog", config={"host": "10.0.0.5"}, enabled=True, status="connected"),
        Integration(name="Slack Alerts", type="webhook", config={"url": "https://hooks.slack.com/..."}, enabled=True, status="configured")
    ]
    for i in integrations:
        db.merge(i)

    db.commit()


def main():
    print("Starting full-stack DB seed...")
    db = SessionLocal()
    try:
        create_db_and_tables()
        seed_organizations(db)
        seed_roles_users(db)
        seed_sources(db)
        seed_parsers(db)
        seed_real_events(db)
        seed_rules_intel_integrations(db)
        print("Seeding complete!")
    except Exception as e:
        print(f"Error seeding DB: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
