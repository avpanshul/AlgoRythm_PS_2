import json
import time
import sys
import traceback
from app.core.messaging import get_kafka_consumer
from app.core.database import SessionLocal
from app.core.search import get_opensearch_client
from app.core.config import settings
from app.models.all import RawEventMetadata
from app.parsers.format_detector import detect_format
from app.parsers.deterministic import parse_log
from app.normalizers.canonical import normalize_event
from app.risk.engine import risk_engine
from app.correlation.engine import correlation_engine
from app.ai.drain3_engine import drain3_engine

def process_message(msg_value: dict, db):
    event_id = msg_value["event_id"]
    
    # 1. Fetch Raw Event Meta
    meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == event_id).first()
    if not meta:
        print(f"Skipping {event_id}: Metadata not found")
        return
        
    # We would normally read from MinIO here, but for simplicity in this prototype,
    # let's assume the raw log content was sent in the Kafka msg if we didn't want to make an HTTP call,
    # wait, we didn't send raw_log in the kafka msg. We MUST read from MinIO to fulfill the requirement.
    from app.core.storage import get_minio_client
    minio_client = get_minio_client()
    try:
        response = minio_client.get_object(settings.MINIO_RAW_BUCKET, meta.raw_location)
        raw_log = response.read().decode('utf-8')
    finally:
        response.close()
        response.release_conn()

    # 2. Format Detection
    format_info = detect_format(raw_log)
    
    # 3. Parsing (Deterministic or Template)
    if format_info["format"] != "UNKNOWN":
        parsed_data = parse_log(raw_log, format_info["format"])
    else:
        # Unknown Log Intelligence (Drain3)
        template_result = drain3_engine.extract_template(raw_log)
        cluster_id = str(template_result.cluster_id)
        template_str = template_result.get_template()
        
        # We should store the template in Postgres here (omitted for brevity, assume updated on read)
        
        variables = drain3_engine.get_variables(raw_log, template_str)
        parsed_data = {
            "header": {"vendor": "UNKNOWN", "product": "UNKNOWN_DEVICE"},
            "fields": variables
        }
        format_info["format"] = f"Template_{cluster_id}"
        
    # 4. Canonical Normalization (Includes Semantic Mapping & Local LLM fallback inside)
    meta_dict = {
        "event_id": meta.event_id,
        "received_at": meta.received_at.isoformat(),
        "raw_sha256": meta.raw_sha256
    }
    canonical = normalize_event(db, parsed_data, meta_dict, format_info)
    
    # 5. Correlation & Risk Engine
    corr_results = correlation_engine.track_and_correlate(canonical)
    risk_results = risk_engine.calculate_risk(
        canonical, 
        correlation_score=corr_results["correlation_score"],
        frequency_score=corr_results["frequency_score"]
    )
    
    # Attach risk to canonical event
    canonical_dict = canonical.model_dump()
    canonical_dict["risk"] = risk_results
    
    # 6. Index into OpenSearch
    os_client = get_opensearch_client()
    os_client.index(
        index=settings.OPENSEARCH_INDEX,
        body=canonical_dict,
        id=canonical.event_id
    )
    
    # Update status
    meta.processing_status = "processed"
    db.commit()
    print(f"Successfully processed {event_id}")

def run_worker():
    print("Starting Kafka worker...")
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
            val = json.loads(msg.value().decode('utf-8'))
            process_message(val, db)
        except Exception as e:
            print(f"Error processing message: {e}")
            traceback.print_exc()
            # Send to DLQ (not implemented)
            
if __name__ == "__main__":
    time.sleep(10) # Wait for other services to start
    run_worker()
