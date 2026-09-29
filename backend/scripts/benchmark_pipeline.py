"""Measures actual end-to-end pipeline throughput: format detection -> parse ->
normalize -> redact -> risk score -> RFC 8785 canonicalize+hash -> Merkle
append -> signed checkpoint -> DB commit, run against a real (if temporary)
database and filesystem, not a synthetic in-memory loop.

Caveats, stated up front rather than left for a reader to discover:
  - Runs against local SQLite, not production Postgres, and a temp directory
    for the raw vault, not MinIO/network storage. Numbers are single-process,
    single-machine, and will differ (likely worse) against real Postgres over
    a network and real disk I/O.
  - "Per-event checkpoint" is on in this codepath (see core/processing.py) --
    every ingested event re-signs a fresh Ed25519 checkpoint over the whole
    Merkle log so far, so per-event cost grows with total events processed.
    This is a known, called-out tradeoff (a real deployment would batch
    checkpoints on a timer), and this benchmark measures it as configured,
    not a hypothetical batched version.
  - No socket/HTTP layer is involved -- this measures the pipeline function
    directly, not requests through FastAPI/uvicorn.

Usage: POSTGRES_PASSWORD=x python scripts/benchmark_pipeline.py [N]
"""
import os
import sys
import json
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("POSTGRES_PASSWORD", "x")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.database as database
database.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)

import app.core.local_storage as local_storage
local_storage.DATA_DIR = tempfile.mkdtemp(prefix="ulpf_bench_raw_")

from app.models import all as models  # noqa: E402  (must import after engine swap)
database.Base.metadata.create_all(bind=database.engine)

from app.core.processing import process_raw_event  # noqa: E402

SAMPLE_LOGS = [
    lambda i: f'<134>1 2026-09-24T10:{i%60:02d}:00Z FW-Delhi-{i%5:02d} - - - msg="Intrusion Detected" src_ip=192.168.1.{i%255} dst_ip=203.0.113.{i%255} action=BLOCK proto=TCP dpt=22 spt=49231 rule="IDS-SSH-Brute"',
    lambda i: json.dumps({"event": {"category": "authentication", "action": "login_failure", "severity": "high"}, "source_ip": f"10.0.0.{i%255}", "message": f"failed login attempt {i}"}),
    lambda i: f"CEF:0|PaloAlto|PAN-OS|10.1|4000|Traffic Deny|7|src=192.168.2.{i%255} dst=10.0.0.{i%255} dpt=443 act=deny",
]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    db = database.SessionLocal()

    durations = []
    t_start = time.perf_counter()
    for i in range(n):
        raw_log = SAMPLE_LOGS[i % len(SAMPLE_LOGS)](i)
        event_id = f"bench_{i:06d}"
        raw_sha256 = "0" * 64  # not the point of this benchmark; real hash computed inside the pipeline
        t0 = time.perf_counter()
        process_raw_event(db, event_id, raw_log, "UNKNOWN", raw_sha256, f"bench/{event_id}.txt")
        durations.append(time.perf_counter() - t0)
    total = time.perf_counter() - t_start

    durations.sort()
    p50 = durations[len(durations) // 2]
    p95 = durations[int(len(durations) * 0.95)]
    p99 = durations[int(len(durations) * 0.99)]

    result = {
        "events": n,
        "total_seconds": round(total, 3),
        "events_per_second": round(n / total, 1),
        "p50_ms": round(p50 * 1000, 2),
        "p95_ms": round(p95 * 1000, 2),
        "p99_ms": round(p99 * 1000, 2),
        "environment": "local SQLite (in-memory), local temp filesystem, single process, per-event checkpoint signing ON",
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
