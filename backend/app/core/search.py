from opensearchpy import OpenSearch
from app.core.config import settings

def get_opensearch_client() -> OpenSearch:
    return OpenSearch(
        hosts=[settings.OPENSEARCH_URL],
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False
    )

def init_opensearch():
    client = get_opensearch_client()
    index_name = settings.OPENSEARCH_INDEX
    if not client.indices.exists(index=index_name):
        mapping = {
            "mappings": {
                "properties": {
                    "timestamp": {"type": "date"},
                    "event_id": {"type": "keyword"},
                    "event": {
                        "properties": {
                            "category": {"type": "keyword"},
                            "type": {"type": "keyword"},
                            "action": {"type": "keyword"},
                            "severity": {"type": "keyword"},
                            "outcome": {"type": "keyword"}
                        }
                    },
                    "source": {
                        "properties": {
                            "ip": {"type": "ip"},
                            "port": {"type": "integer"}
                        }
                    },
                    "destination": {
                        "properties": {
                            "ip": {"type": "ip"},
                            "port": {"type": "integer"}
                        }
                    },
                    "risk": {
                        "properties": {
                            "score": {"type": "integer"},
                            "level": {"type": "keyword"}
                        }
                    }
                }
            }
        }
        client.indices.create(index=index_name, body=mapping)
