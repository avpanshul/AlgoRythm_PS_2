FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    librdkafka-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Pre-install PyTorch (CPU only for lightweight local dev) to save time for Sentence Transformers
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

# Real air-gap blocker found live: app/ai/embeddings.py's EmbeddingEngine
# instantiates SentenceTransformer(settings.EMBEDDING_MODEL) at import time,
# which downloads the model from HuggingFace Hub on first use if it isn't
# already cached on disk -- silently breaking in a genuinely air-gapped
# deployment (no error until something actually triggers that import path,
# then a hang/failure reaching huggingface.co). Pre-downloading it here, at
# build time (when the builder legitimately has network access), bakes the
# weights into this image layer so no network call happens at runtime
# regardless of AIRGAPPED_MODE. HF_HOME pinned to a path under /app so the
# cache is both inside this layer and readable by the non-root `ulpf` user
# created below.
ENV HF_HOME=/app/.cache/huggingface
RUN python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ.get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'))"

COPY . .

ENV PYTHONPATH=/app
# Real bug found via a live kind-cluster smoke test: without this, Python's
# stdout is block-buffered when not attached to a TTY (true for every
# container), so print()-based diagnostics (including a real startup
# migration failure) sat unflushed and invisible to `kubectl logs` --
# masking the actual bug rather than just being unrelated noise.
ENV PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 1000 ulpf && chown -R ulpf:ulpf /app
USER ulpf

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",8000)}/api/v1/health')" || exit 1

# Shell form (not exec-form JSON array) so $PORT actually expands -- hosts
# like Render assign a dynamic port via the PORT env var and route traffic
# to it; a hardcoded --port 8000 here would make the container listen on a
# port the platform never sends requests to, and the deploy would look
# "successful" while every request 502s. Falls back to 8000 for plain
# `docker run`/docker-compose, where PORT is normally unset.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
