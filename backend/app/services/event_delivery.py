r"""Real-time downstream delivery of newly-ingested events: webhook export
(Item g, SIEM/Data Lake integration) and OpenSearch indexing.

Both pieces close a real gap: the `Integration` model (webhook/rest_api/
syslog/s3/opensearch) and `app/core/search.py`'s OpenSearch client+index
mapping already existed, but nothing ever actually called them per-event --
`init_opensearch()` only ever created the index once at startup, and no
webhook delivery code existed at all.

Deliberately called ONLY from real-time ingestion (process_raw_event's
default `deliver=True`), never from seed.py's bulk historical backfill
(`deliver=False` there, explicitly) -- firing tens of thousands of webhook
POSTs / OpenSearch index calls for a one-time historical reseed would flood
a demo webhook endpoint and add real latency/CPU pressure to a process this
project has already OOM'd more than once this deployment's lifetime. Live,
newly-arriving events are the real use case for "push this out to my SIEM
the moment it happens" -- a historical backfill is not.

Both functions are deliberately silent-but-safe on failure: a downstream
system being unreachable (OpenSearch isn't deployed anywhere reachable from
this instance in production, by design -- see docs) must never fail, slow
down, or retry-queue against the actual ingestion request. No in-memory
queue, no retry loop -- exactly the unbounded-growth pattern this project's
own history (correlation.py, sentinel.py) already paid for twice this
session. A failed delivery is just a failed delivery; the next real event
tries again independently.
"""
import logging

import requests

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.all import Integration

log = logging.getLogger("event_delivery")

WEBHOOK_TIMEOUT_SECONDS = 5
OPENSEARCH_TIMEOUT_SECONDS = 3


def deliver_to_webhooks(db: Session, canonical: dict) -> None:
    """POSTs the real canonical event to every enabled webhook Integration's
    configured URL. One real HTTP call per configured webhook, per event --
    short timeout, never raises, never queues. `last_test_at`/
    `last_test_result` are updated with the real outcome so the Integrations
    page reflects genuine delivery history, not a static "configured" label.

    AIRGAPPED_MODE skips this entirely: a webhook's configured URL is
    arbitrary operator input, unlike OPENSEARCH_URL/OLLAMA_URL which in a
    real docker-compose deployment point at containers on the same internal
    network. There's no way to know from here whether a given webhook URL
    stays inside an air-gapped network or reaches out to the real internet,
    so the safe default is to not attempt it at all."""
    if settings.AIRGAPPED_MODE:
        return
    webhooks = db.query(Integration).filter(Integration.type == "webhook", Integration.enabled == True).all()  # noqa: E712
    if not webhooks:
        return
    for integration in webhooks:
        url = (integration.config or {}).get("url")
        if not url:
            continue
        try:
            resp = requests.post(url, json=canonical, timeout=WEBHOOK_TIMEOUT_SECONDS)
            integration.status = "connected" if resp.ok else "error"
            integration.last_test_result = {"http_status": resp.status_code, "event_id": canonical.get("event_id")}
        except Exception as e:  # noqa: BLE001 -- a downstream outage must never break ingestion
            integration.status = "error"
            integration.last_test_result = {"error": str(e)[:300], "event_id": canonical.get("event_id")}
            log.info("webhook delivery to %s failed (will retry on next event, not queued): %s", url, e)
        finally:
            from datetime import datetime, timezone
            integration.last_test_at = datetime.now(timezone.utc)
    db.commit()


def index_to_opensearch(canonical: dict) -> None:
    """Indexes the real canonical event into OpenSearch, matching the index
    mapping app/core/search.py:init_opensearch() already creates at startup.
    Unreachable (the real, honest state of this deployment's production
    environment -- no OpenSearch instance is deployed anywhere reachable
    from Render) is treated as a normal, expected outcome: logged once at
    debug level, never raised, never retried."""
    try:
        from app.core.search import get_opensearch_client
        client = get_opensearch_client()
        doc = {
            "timestamp": canonical.get("timestamp"),
            "event_id": canonical.get("event_id"),
            "event": canonical.get("event"),
            "source": canonical.get("source"),
            "destination": canonical.get("destination"),
            "risk": canonical.get("risk"),
        }
        client.index(
            index=settings.OPENSEARCH_INDEX,
            id=canonical.get("event_id"),
            body=doc,
            params={"timeout": f"{OPENSEARCH_TIMEOUT_SECONDS}s"},
            request_timeout=OPENSEARCH_TIMEOUT_SECONDS,
        )
    except Exception as e:  # noqa: BLE001 -- OpenSearch being unreachable must never break ingestion
        log.debug("OpenSearch indexing skipped (unreachable or erroring, not queued): %s", e)
