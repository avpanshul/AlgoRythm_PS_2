r"""Async ingestion worker (ULPF-phase2-prompt.md E5: pluggable ingestion
backend). Consumes the "raw-events" topic that api/v1/ingestion.py publishes
to when INGEST_BACKEND=kafka, and runs each event through the exact same
app.core.processing.process_raw_event() the synchronous ("sync", default)
path uses directly in the request handler -- so an event's outcome
(normalization, risk score, Merkle inclusion, DLQ-on-failure) is identical
regardless of which ingestion backend produced it.

History note: an earlier version of this file ran its own separate,
incomplete pipeline (app/normalizers/canonical.py + app/risk/engine.py +
app/correlation/engine.py, indexing only into OpenSearch). That pipeline
never wrote to the NormalizedEvent table the rest of this application
actually reads from, skipped PII redaction and Merkle/integrity hashing
entirely, and was never fed any input in practice -- nothing in
api/v1/ingestion.py ever published to the topic it consumed, in any
deployment mode, so it was dead code masquerading as a working worker
container in docker-compose.yml. Rewritten to delegate to the real pipeline
instead of maintaining a second, divergent one.
"""
import json
import time
import traceback

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.local_storage import read_raw_log
from app.core.messaging import get_kafka_consumer
from app.core.processing import process_raw_event


def process_message(msg_value: dict, db):
    event_id = msg_value["event_id"]
    source_id = msg_value["source_id"]
    raw_sha256 = msg_value["raw_sha256"]
    raw_location = msg_value["raw_location"]

    raw_log = read_raw_log(raw_location)
    process_raw_event(db, event_id, raw_log, source_id, raw_sha256, raw_location)
    print(f"Processed {event_id} via async (kafka) ingestion backend")


def run_worker():
    print(f"Starting async ingestion worker (INGEST_BACKEND={settings.INGEST_BACKEND})...")
    consumer = get_kafka_consumer("ulp_worker_group")
    consumer.subscribe(["raw-events"])

    db = SessionLocal()
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue

        try:
            val = json.loads(msg.value().decode("utf-8"))
            process_message(val, db)
        except Exception:
            # process_raw_event already routes its own failures to the DLQ;
            # anything raised here (e.g. the raw log file itself missing)
            # is a worker-level problem, not an event-level one -- log and
            # keep consuming rather than crash the whole worker on one bad
            # message.
            traceback.print_exc()


if __name__ == "__main__":
    time.sleep(10)  # wait for other compose services to start
    run_worker()
