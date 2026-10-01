# Sanket — Universal Log Pre-processing Framework (ULPF)

Sanket normalizes log data from any source format (Syslog, JSON, XML, CSV, CEF, LEEF, KeyValue, and more) into a single canonical schema, then runs real-time correlation, behavioral risk scoring, and cryptographic integrity sealing on top of it — before any of it reaches a dashboard or an analyst.

**Live demo:** https://algorhythm-ulpf-frontend.vercel.app
**Backend API:** https://algorhythm-ulpf-backend.onrender.com (interactive docs at `/docs`)

Sign in with the **"Fill Demo Credentials"** button on the login page (a real, low-privilege demo account), or create your own account via Sign Up.

---

## What's in here

- **Ingestion & normalization** — HTTP, syslog (UDP/TCP, optional mTLS), and batch ingestion; deterministic + LLM-assisted field mapping to a common ECS-like schema
- **Parser Lab** — write, test, version, and publish parsers for new log formats through a real approval workflow
- **Correlation engine** (`app/analytics/correlation.py`) — YAML-defined, cross-source, multi-stage attack pattern rules
- **Sentinel** (`app/ai/sentinel.py`) — per-entity behavioral risk profiling, fully explainable (every score change has a real reason log, never a black-box number)
- **Attack Path reconstruction + Sparks** — real, time-ordered incident paths, auto-triggered by correlation matches or risk-score thresholds; advisory only, never predictive
- **Integrity & Replay** — Merkle-tree event sealing with inclusion proofs, checkpointing, and reprocessing/replay jobs
- **Privacy policies & retention** — configurable redaction rules and per-source retention windows, with legal-hold support
- **Threat intelligence** — indicator matching against ingested events
- **Live detection loop** — a background cycle that runs correlation + Sentinel continuously (not just on manual request) and auto-opens Cases with notifications for high/critical findings

---

## Tech stack

| Layer | Stack |
|---|---|
| Backend | FastAPI (Python 3.11), SQLAlchemy, PostgreSQL |
| Frontend | React 19 + TypeScript, Vite, TanStack Query, Recharts |
| Optional infra | Kafka-compatible ingestion (Redpanda), MinIO (raw event storage), OpenSearch, Redis, Ollama (LLM field mapping) |
| Deployment | Render (backend + Postgres), Vercel (frontend) |

---

## Setup

You have two options: a quick local demo with no Docker/Postgres required, or the full stack via Docker Compose.

### Option A — Quick local demo (fastest, no Docker needed)

Runs the whole backend against a local SQLite file instead of Postgres. Good for trying the UI without any infra setup.

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python scripts/run_local_demo.py
```

This starts the API on `http://localhost:8000` and creates an admin account:
`admin@ulpf.local` / `local-demo-admin-pw`

```bash
# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. To load it with real sample data (loghub, Zeek, CloudTrail, EVTX corpora — see `backend/datasets/real/`), run:

```bash
cd backend
python seed.py
```

### Option B — Full stack via Docker Compose

Brings up Postgres, MinIO, OpenSearch, Redis, Redpanda (Kafka-compatible), Ollama, the backend API, a background worker, the syslog listener, and the frontend — all together.

```bash
cp .env.example .env   # create this if it doesn't exist; see "Environment variables" below
docker compose up --build
```

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000` (docs at `/docs`)
- MinIO console: `http://localhost:9001`
- OpenSearch Dashboards: `http://localhost:5601`
- Syslog listener: UDP/TCP `5514`, mTLS TCP `6514` (opt-in, see `docs/PKI.md`)

---

## Environment variables

Set these in `backend/.env` (Docker Compose) or your shell (local demo already sets sane defaults for most of these).

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | — | Full Postgres connection string; takes priority over the individual `POSTGRES_*` vars if set (handles managed hosts like Render/Heroku) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_HOST` / `POSTGRES_PORT` | `ulp` / — / `ulp_db` / `localhost` / `5432` | Used if `DATABASE_URL` isn't set |
| `JWT_SECRET` | auto-generated | **Set this explicitly for anything beyond local demo** (`openssl rand -hex 32`) — without it, a random secret is generated per-process and all tokens are invalidated on restart |
| `ADMIN_INITIAL_EMAIL` / `ADMIN_INITIAL_PASSWORD` | `admin@ulpf.local` / — | If `ADMIN_INITIAL_PASSWORD` is set, an admin account is bootstrapped on first startup (only if no users exist yet) |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:5174,http://localhost:3000` | Comma-separated allowlist |
| `OLLAMA_URL` / `OLLAMA_MODEL` / `OLLAMA_TIMEOUT_SECONDS` | `http://localhost:11434` / `llama3.2:latest` / `90` | LLM-assisted field mapping; falls back gracefully to `UNKNOWN` if unreachable |
| `INGEST_BACKEND` | `sync` | `sync` processes events immediately in the request handler; `kafka` defers normalization/scoring to the worker via Redpanda |
| `KAFKA_BROKERS` | `localhost:9092` | Only relevant if `INGEST_BACKEND=kafka` |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | `localhost:9000` / `admin` / — | Raw event storage |
| `OPENSEARCH_URL` | `http://localhost:9200` | |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Used by the embedding-based field mapper |

Frontend (`frontend/.env` or Vite env vars):

| Variable | Default (dev) | Notes |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/api/v1` | Backend base URL |
| `VITE_DEMO_EMAIL` / `VITE_DEMO_PASSWORD` | falls back to `admin@ulpf.local` / `local-demo-admin-pw` | Powers the "Fill Demo Credentials" button — use a real, dedicated low-privilege account in production, never the real admin password (these are baked into the public JS bundle) |

---

## Project structure

```
backend/
  app/
    api/v1/           REST endpoints
    core/              config, database, security, processing pipeline
    analytics/          correlation engine + YAML rules
    ai/                 Sentinel, LLM field mapping, deterministic mapping
    services/            pack drafting, live detection loop, retention
    parsers/              format detection + per-format parsers
    models/                SQLAlchemy models
  datasets/real/        real seeded log corpora + builder scripts
  seed.py                 real-data bootstrap script
  scripts/run_local_demo.py  no-Docker local runner (SQLite)

frontend/
  src/
    pages/              one file per screen (Dashboard, Parser Lab, Attack Path, ...)
    components/          shared UI (Sidebar, GlassCard, ...)
    api/client.ts         typed API client
    layouts/AppLayout.tsx  shared sidebar + main content shell
```

---

## Notes

- All seeded demo data comes from real, publicly available log corpora (loghub, Zeek/Bro IDS output, AWS CloudTrail attack-simulation data, Windows Event Log attack-technique captures) — nothing in the dataset is synthetically generated.
- Risk scores, correlation matches, and attack paths are computed live against whatever real data is actually ingested; empty states are shown honestly rather than padded with placeholder data.
