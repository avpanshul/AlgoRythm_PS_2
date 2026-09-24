"""Seed script for Demo Mode (PostgreSQL-only)."""
import os
import sys
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
import yaml

# Ensure we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.all import Base, Source, User, Role, Organization, CorrelationRule, Parser, ParserVersion, ThreatIndicator, Integration, PrivacyPolicy, NormalizedEvent, RawEventMetadata, AuditLog, DLQEvent

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
    print("Seeding sources...")
    sources = [
        Source(id="FW-001", name="Palo Alto Edge", vendor="Palo Alto", product="PAN-OS", device_type="Firewall", organization_id="ORG-MEITY"),
        Source(id="SYS-LNX", name="Core Linux Servers", vendor="Linux", product="Syslog", device_type="Server", organization_id="ORG-NIC"),
        Source(id="WEB-01", name="Nginx Frontends", vendor="F5", product="Nginx", device_type="Proxy", organization_id="ORG-MEITY"),
        Source(id="EDR-01", name="CrowdStrike Agents", vendor="CrowdStrike", product="Falcon", device_type="EDR", organization_id="ORG-CERT"),
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

def seed_events(db: Session):
    print("Seeding events (normalized & raw)...")
    now = datetime.now(timezone.utc)
    
    # Successful events
    for i in range(100):
        evt_time = now - timedelta(minutes=i*15)
        evt_id = f"evt_demo_{i}"
        raw = f"Sample raw log {i} from 10.0.0.{i%255}"
        sha = hashlib.sha256(raw.encode()).hexdigest()
        
        meta = RawEventMetadata(
            event_id=evt_id, source_id="FW-001" if i%2==0 else "SYS-LNX",
            received_at=evt_time, ingestion_protocol="syslog",
            raw_sha256=sha, raw_location=f"2026/09/23/{evt_id}.txt",
            processing_status="normalized"
        )
        db.merge(meta)
        
        norm = NormalizedEvent(
            event_id=evt_id, timestamp=evt_time, source_id="FW-001" if i%2==0 else "SYS-LNX",
            source_ip=f"10.0.0.{i%255}", dest_ip="192.168.1.100",
            action="Connection Allowed" if i%5!=0 else "Connection Denied",
            severity="info" if i%5!=0 else "high",
            risk_level="LOW" if i%5!=0 else "HIGH",
            risk_score=10 if i%5!=0 else 75,
            message=raw, parser_format="Syslog", quality_score=85,
            canonical_json={"event_id": evt_id, "timestamp": evt_time.isoformat(), "event": {"action": "test", "severity": "info"}}
        )
        db.merge(norm)
    
    # DLQ Events
    for i in range(5):
        evt_id = f"evt_dlq_{i}"
        dlq = DLQEvent(
            event_id=evt_id, source_id="WEB-01", raw_log="Malformed log...",
            failure_reason="ValueError", failure_detail="Invalid date format",
            status="failed", retry_count=i%3
        )
        db.merge(dlq)
        
    db.commit()

def seed_rules_intel_integrations(db: Session):
    print("Seeding rules, intel, and integrations...")
    rules = [
        CorrelationRule(name="Brute Force Attempt", severity="high", enabled=True, threshold=5, time_window_seconds=60, condition={"field": "action", "value": "login_failed"}),
        CorrelationRule(name="Data Exfiltration", severity="critical", enabled=True, threshold=1000000, time_window_seconds=3600, condition={"field": "bytes_out", "operator": ">"})
    ]
    for r in rules: db.merge(r)
    
    intel = [
        ThreatIndicator(type="ip", value="203.0.113.99", threat_type="C2 Server", severity="critical"),
        ThreatIndicator(type="domain", value="evil-domain.test", threat_type="Phishing", severity="high")
    ]
    for i in intel: db.merge(i)
        
    integrations = [
        Integration(name="Splunk Forwarder", type="syslog", config={"host": "10.0.0.5"}, enabled=True, status="connected"),
        Integration(name="Slack Alerts", type="webhook", config={"url": "https://hooks.slack.com/..."}, enabled=True, status="configured")
    ]
    for i in integrations: db.merge(i)
        
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
        seed_events(db)
        seed_rules_intel_integrations(db)
        print("Seeding complete! ✨")
    except Exception as e:
        print(f"Error seeding DB: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
