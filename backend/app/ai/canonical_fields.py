"""The canonical ECS-like field vocabulary used by both the embedding-based
mapper (app/ai/embeddings.py) and the LLM-based mapper (app/ai/llm.py).

Split out on its own so importing it never drags in sentence-transformers/
torch: app/ai/llm.py only ever needs this plain list of strings (to build its
prompt and validate the model's answer), never the embedding model itself --
importing app/ai/embeddings.py for that used to force-instantiate its
module-level EmbeddingEngine() (a real SentenceTransformer load + 16 real
embedding computations) inside whatever request happened to trigger the
first LLM-fallback field classification. Confirmed live: this OOM-killed the
backend (Render's own oomKilled event, 512Mi limit) the first time a real
Add Source wizard sample hit a field the deterministic table didn't know.
"""

CANONICAL_FIELDS = [
    "source.ip",
    "source.port",
    "destination.ip",
    "destination.port",
    "event.action",
    "event.category",
    "event.type",
    "event.severity",
    "event.outcome",
    "network.protocol",
    "network.transport",
    "user.name",
    "device.id",
    "device.vendor",
    "device.product",
    "timestamp",
]
