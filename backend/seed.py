"""Seed script for Demo Mode (PostgreSQL-only).

2026-09-25: stopped seeding fabricated organizations, users, sources, threat
indicators and integrations -- those are entity/record data that looked like
real production state but weren't (invented org names, placeholder emails,
non-resolvable "threat" indicators, fake integration endpoints). Per explicit
instruction: no invented logs/events, users/organizations, alerts/threats,
source health, threat intelligence, or integrations -- a fresh install now
starts with none of these and shows honest empty states until a real admin
adds real ones (see app/main.py's ADMIN_INITIAL_PASSWORD-driven seed for the
one account a fresh install does get, from an env var, not a hardcoded name).

Still seeded, and still legitimate: Role *definitions* (a permission
taxonomy, not a claim that a real person holds that role), CorrelationRule
*definitions* (detection logic, not a claim that a real alert fired), and
Parser *definitions* (processing config, not a claim about real traffic seen)
-- these describe how the system is configured, not what has happened.

Event data is NOT fabricated. seed_real_events() reads real, publicly
downloaded log lines from backend/datasets/real/ and feeds every line through
the ACTUAL production pipeline (app/core/processing.py:process_raw_event),
the same code path app/api/v1/ingestion.py:process_single_log() uses for
live ingestion. parser_format, risk_score, risk_level, quality_score and
canonical_json on every seeded NormalizedEvent are therefore real pipeline
output, not hardcoded values. Lines the deterministic parser can't handle
correctly land in DLQEvent, exactly as they would in production -- that is
the pipeline's real fallback behavior, not simulated failure data.

Four real corpora are seeded, each with its own provenance doc in its
builder script:
  - datasets/real/build_corpus.py            -- logpai/loghub (Linux, OpenSSH,
    Mac, Apache, HDFS, Hadoop, Zookeeper, Windows, HPC, BGL raw samples)
  - datasets/real/build_evtx_corpus.py       -- sbousseaden/EVTX-ATTACK-SAMPLES
    (real Windows Event Logs from actual attack-technique execution, MIT)
  - datasets/real/build_zeek_corpus.py       -- real Zeek/Bro IDS engine output
    (user-supplied dataset dump; malware/notice/ssl/dhcp/ftp/irc/app_stats)
  - datasets/real/build_cloudtrail_corpus.py -- invictus-ir/aws_dataset (MIT)
    -- real AWS CloudTrail from a Stratus Red Team attack simulation
"""
import os
import sys
import time
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
    Base, Source, Role, CorrelationRule, Parser,
    RawEventMetadata,
)

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets", "real")
CORPUS_PATH = os.path.join(DATASET_DIR, "corpus.jsonl")
EVTX_CORPUS_PATH = os.path.join(DATASET_DIR, "evtx_corpus.jsonl")
ZEEK_CORPUS_PATH = os.path.join(DATASET_DIR, "zeek_corpus.jsonl")
CLOUDTRAIL_CORPUS_PATH = os.path.join(DATASET_DIR, "cloudtrail_corpus.jsonl")


def create_db_and_tables():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)


def seed_sources_for_real_data(db: Session):
    """Registers only the 5 Source rows that seed_real_events() actually
    attributes real loghub-derived events to -- NormalizedEvent.source_id is
    a real foreign key, so these have to exist for that real data to load.
    No fabricated device names or organization references: vendor/product
    describe the actual real dataset behind each one (see
    datasets/real/build_corpus.py's FILES mapping). The two sources the old
    seed had with zero real data behind them ("Palo Alto Edge", "CrowdStrike
    Agents") are gone, not replaced -- there's nothing real to attribute to them."""
    print("Seeding sources for real loghub-derived data...")
    sources = [
        Source(id="SYS-LNX", name="Linux/Mac/OpenSSH system logs", vendor="loghub", product="Linux_2k/Mac_2k/OpenSSH_2k", device_type="Server"),
        Source(id="WEB-01", name="Apache web server logs", vendor="loghub", product="Apache_2k", device_type="Server"),
        Source(id="DIST-01", name="HDFS/Hadoop/Zookeeper logs", vendor="loghub", product="HDFS_2k/Hadoop_2k/Zookeeper_2k", device_type="Application"),
        Source(id="WIN-01", name="Windows system logs", vendor="loghub", product="Windows_2k", device_type="Server"),
        Source(id="HPC-01", name="HPC/BlueGene system logs", vendor="loghub", product="HPC_2k/BGL_2k", device_type="Server"),
        # sbousseaden/EVTX-ATTACK-SAMPLES (MIT) -- real Windows Event Logs from
        # actual attack-technique execution, MITRE ATT&CK-tagged.
        Source(id="WINEVT-ATTACK", name="Windows Event Log (attack-technique captures)", vendor="EVTX-ATTACK-SAMPLES", product="evtx_data.csv", device_type="Server"),
        # Real Zeek/Bro IDS engine output (user-supplied dataset dump).
        Source(id="ZEEK-NOTICE", name="Zeek IDS notices", vendor="Zeek", product="notice.log", device_type="ids"),
        Source(id="ZEEK-SSL", name="Zeek TLS/SSL log", vendor="Zeek", product="ssl.log", device_type="ids"),
        Source(id="ZEEK-DHCP", name="Zeek DHCP log", vendor="Zeek", product="dhcp.log", device_type="ids"),
        Source(id="ZEEK-DPD", name="Zeek dynamic protocol detection log", vendor="Zeek", product="dpd.log", device_type="ids"),
        Source(id="ZEEK-FTP", name="Zeek FTP log", vendor="Zeek", product="ftp.log", device_type="ids"),
        Source(id="ZEEK-IRC", name="Zeek IRC log", vendor="Zeek", product="irc.log", device_type="ids"),
        Source(id="ZEEK-APPSTATS", name="Zeek application stats log", vendor="Zeek", product="app_stats.log", device_type="ids"),
        # invictus-ir/aws_dataset (MIT) -- real CloudTrail from an attack simulation.
        Source(id="AWS-CLOUDTRAIL", name="AWS CloudTrail (attack simulation)", vendor="invictus-ir/aws_dataset", product="CloudTrail JSON export", device_type="cloud_audit"),
    ]
    for s in sources:
        db.merge(s)
    db.commit()


def seed_roles(db: Session):
    """Role *definitions* only -- a permission taxonomy, not a claim that a
    real person holds any of these roles. No User rows are seeded here
    anymore; the only account a fresh install gets is the one app/main.py
    creates from ADMIN_INITIAL_PASSWORD, if set."""
    print("Seeding role definitions...")
    roles = [
        Role(name="admin", permissions=["all"]),
        Role(name="analyst", permissions=["read_events", "read_alerts"]),
        Role(name="parser_author", permissions=["write_parsers", "read_events"]),
        # Separate from parser_author by design (ULPF-master-prompt.md Part D1,
        # separation of duties): a parser_author can draft/edit a parser but
        # cannot publish it -- see app/api/v1/parsers_api.py:publish_parser,
        # which also blocks self-publish even for this role.
        Role(name="approver", permissions=["approve_parsers", "approve_mappings", "read_events"]),
        Role(name="auditor", permissions=["read_audit_logs", "read_events"]),
        Role(name="collector_operator", permissions=["ingest_events"]),
    ]
    for r in roles:
        existing = db.query(Role).filter(Role.name == r.name).first()
        if not existing:
            db.add(r)
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


def _ensure_corpus(corpus_path: str, builder_module: str):
    """Builds a datasets/real/*.jsonl corpus from its source files if missing."""
    if os.path.exists(corpus_path):
        return
    print(f"{corpus_path} not found, building it via {builder_module}.build() ...")
    sys.path.insert(0, DATASET_DIR)
    module = __import__(builder_module)
    module.build()


def seed_real_events(db: Session, limit: int = None, corpus_path: str = None, builder_module: str = "build_corpus", label: str = "log"):
    """
    Feed real, downloaded log lines through the actual processing pipeline
    (app.core.processing.process_raw_event) -- same code path production
    ingestion uses. Every parser_format / risk_score / quality_score /
    canonical_json value that lands in Postgres comes from that real run,
    not from this script. `corpus_path` defaults to the original loghub
    corpus; pass EVTX_CORPUS_PATH/ZEEK_CORPUS_PATH to seed those too.
    """
    corpus_path = corpus_path or CORPUS_PATH
    _ensure_corpus(corpus_path, builder_module)
    if not os.path.exists(corpus_path):
        print(f"WARNING: {corpus_path} still missing -- skipping real {label} event seed.")
        return {"ok": 0, "dlq": 0, "formats": {}}

    with open(corpus_path, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if limit:
        rows = rows[:limit]

    print(f"Seeding {len(rows)} real {label} events through the real pipeline...")

    format_counts = {}
    ok_count = 0
    dlq_count = 0
    skipped_count = 0

    for row in rows:
        raw_log = row["raw"]
        source_id = row.get("source_id") or "UNKNOWN"

        raw_sha256 = hashlib.sha256(raw_log.encode("utf-8")).hexdigest()

        # Real gap found live: a Render free-tier deploy spun this down mid-run
        # (inbound-HTTP-inactivity idle timeout, independent of this loop's own
        # CPU usage) and killed the process with ~13,800/34,600 events already
        # committed. Without this, re-running main() after a restart would
        # double every already-seeded row. Same dedup-by-raw_sha256 pattern
        # auto_ingest.py already uses for exactly this reason -- makes this
        # loop safely resumable, not just safely re-runnable from empty.
        if db.query(RawEventMetadata).filter(RawEventMetadata.raw_sha256 == raw_sha256).first():
            skipped_count += 1
            continue

        event_id = f"evt_{uuid.uuid4().hex}"
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

        # Real bug found live: this single Session runs for the whole
        # 34,600-row bootstrap (main() opens it once, before calling this
        # function 4 times), and SQLAlchemy's identity map holds a reference
        # to every ORM object it ever loaded or created for the session's
        # entire lifetime unless explicitly released. Confirmed via Render's
        # own memory metrics: usage climbed linearly from 135MB to 465MB
        # against this service's 512MB limit over ~30 minutes, then the
        # process was OOM-killed and silently restarted mid-run (same
        # instance ID, a fresh "Started server process" log line, no deploy,
        # no server_failed event -- exactly what an out-of-process OOM
        # killer looks like from here). expunge_all() detaches every object
        # from the session (safe here: nothing after this point in the loop
        # holds a reference to a prior iteration's rows), capping memory to
        # roughly one batch's worth instead of the whole run's.
        if (ok_count + dlq_count) % 200 == 0:
            db.expunge_all()

        # Real bug found live, after the memory fix above: this loop runs on
        # a background thread (app/api/v1/admin.py's bootstrap endpoint,
        # since 34k+ rows would exceed any HTTP request timeout), but Python
        # threads share one GIL -- a long CPU-bound stretch with no I/O wait
        # (confirmed via Render's own CPU metrics: pegged at this service's
        # 0.15 vCPU cap continuously for 8+ minutes with zero log output,
        # coinciding with a run of BGL_2k.log lines that end in long runs of
        # repeated dots) can starve the main asyncio thread of GIL time
        # entirely, including the Dockerfile's own /api/v1/health
        # HEALTHCHECK request handler -- which is exactly what a "same
        # instance ID gets a fresh 'Started server process' log line with no
        # deploy and no server_failed event" restart looks like from the
        # outside. time.sleep(0) forces a GIL release without slowing this
        # loop down in any way that matters (real per-row DB round-trips
        # already dominate its running time), giving the health check a
        # chance to actually run instead of queuing behind this thread
        # indefinitely.
        time.sleep(0)

    print(f"  -> {ok_count} NormalizedEvent rows, {dlq_count} DLQEvent rows, {skipped_count} already-seeded rows skipped")
    print(f"  -> format breakdown: {format_counts}")
    return {"ok": ok_count, "dlq": dlq_count, "skipped": skipped_count, "formats": format_counts}


def seed_correlation_rules(db: Session):
    """Detection rule *definitions* only -- these describe logic that would
    fire against real matching events, not a claim that either the rule
    matched or any threat/integration is real. No ThreatIndicator or
    Integration rows are seeded anymore -- those would be claims about real
    threats/connections that don't exist; a real admin adds real ones."""
    print("Seeding correlation rule definitions...")
    rules = [
        CorrelationRule(name="Brute Force Attempt", severity="high", enabled=True, threshold=5, time_window_seconds=60, condition={"field": "action", "value": "login_failed"}),
        CorrelationRule(name="Data Exfiltration", severity="critical", enabled=True, threshold=1000000, time_window_seconds=3600, condition={"field": "bytes_out", "operator": ">"})
    ]
    for r in rules:
        db.merge(r)
    db.commit()


def main():
    print("Starting DB seed (role/parser/rule definitions + real log data only -- no fabricated orgs/users/sources/threat-intel/integrations)...")
    db = SessionLocal()
    try:
        create_db_and_tables()
        seed_roles(db)
        seed_sources_for_real_data(db)
        seed_parsers(db)

        # Publish the 9 vendor source packs *before* seeding real event
        # corpora -- previously this ran as a separate, later manual step
        # (scripts/seed_vendor_packs.py invoked after this script), which
        # meant every real bulk-seeded event went through the hardcoded
        # deterministic normalization fallback and none of the published
        # packs' field_mappings were ever actually exercised by real data,
        # only by each pack's own single canned fixture line. Discovered via
        # the correlation engine (E1) surfacing 0 matches and a `source_ip`/
        # `dest_port` audit showing 100% `mapping_method: deterministic`
        # across all 16,864 seeded events.
        import scripts.seed_vendor_packs as _seed_vendor_packs
        _seed_vendor_packs.main()

        seed_real_events(db, label="loghub")
        seed_real_events(db, corpus_path=EVTX_CORPUS_PATH, builder_module="build_evtx_corpus", label="EVTX-ATTACK-SAMPLES Windows Event Log")
        seed_real_events(db, corpus_path=ZEEK_CORPUS_PATH, builder_module="build_zeek_corpus", label="Zeek/Bro IDS")
        seed_real_events(db, corpus_path=CLOUDTRAIL_CORPUS_PATH, builder_module="build_cloudtrail_corpus", label="AWS CloudTrail")
        seed_correlation_rules(db)
        print("Seeding complete!")
    except Exception as e:
        print(f"Error seeding DB: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
