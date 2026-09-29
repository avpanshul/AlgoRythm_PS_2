# ULPF — Universal Log Pre-processing Framework

**Smart India Hackathon — Problem Statement 26156**

ULPF ingests security logs from heterogeneous sources — firewalls, Windows Event Log, syslog appliances, cloud audit trails, application logs — detects the format automatically, normalizes every event into one canonical schema, redacts PII, scores risk, and makes the result cryptographically tamper-evident with an append-only Merkle tree and signed checkpoints. On top of that pipeline sits a full analyst application: correlation, entity behavior profiling, incident case management, attack-path reconstruction, threat hunting, and parser authoring.

Live-verified at time of writing: **34,626 real ingested events, 99.9% parse success rate, 13 natively supported log formats.** Every dataset shipped is either real third-party log data with a checkable source, or explicitly labeled synthetic — nothing is fabricated to look more complete than it is.

## Documentation

Full technical documentation lives in [`docs/`](docs/):

| Doc | Covers |
|---|---|
| [`01_PROJECT_OVERVIEW.md`](docs/01_PROJECT_OVERVIEW.md) | What this is, the problem, novelty, honest limitations, current status |
| [`02_SYSTEM_ARCHITECTURE.md`](docs/02_SYSTEM_ARCHITECTURE.md) | Backend/frontend architecture, data flow, all routers and models |
| [`03_FEATURES_TECH_STACK_AND_DATA.md`](docs/03_FEATURES_TECH_STACK_AND_DATA.md) | Full feature inventory, tech stack, supported formats, real datasets |
| [`04_TESTING_AND_VERIFICATION.md`](docs/04_TESTING_AND_VERIFICATION.md) | Test strategy, results, and the full test matrix |
| [`05_INTEGRATION_AND_DEPLOYMENT_READINESS.md`](docs/05_INTEGRATION_AND_DEPLOYMENT_READINESS.md) | Deployment checklist, env vars, integration matrix, go/no-go assessment |

## Tech stack

- **Backend:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (SQLite for local dev)
- **Frontend:** React 19, TypeScript, Vite, TanStack Query, Tailwind CSS
- **Integrity:** RFC 6962 Merkle tree, Ed25519 / PKCS#11-HSM signed checkpoints, RFC 3161 trusted timestamps
- **AI/ML:** Drain3 (log clustering), sentence-transformers, Ollama (local LLM assist), a real offline-validated LinUCB alert-triage bandit

See [`docs/03_FEATURES_TECH_STACK_AND_DATA.md`](docs/03_FEATURES_TECH_STACK_AND_DATA.md) for the full breakdown.

## Running it locally

```bash
# Backend (SQLite-backed, no Docker/Postgres needed)
cd backend
pip install -r requirements.txt
python scripts/run_local_demo.py
# -> http://localhost:8000  (Swagger UI at /docs)

# Frontend, in a second terminal
cd frontend
npm install
npm run dev
# -> http://localhost:5173
```

Load real demo data (optional, not required to boot):

```bash
cd backend
python seed.py
python scripts/seed_vendor_packs.py
```

Full setup detail, Docker Compose, and Kubernetes paths are in [`docs/05_INTEGRATION_AND_DEPLOYMENT_READINESS.md`](docs/05_INTEGRATION_AND_DEPLOYMENT_READINESS.md).

## Deployment

Configured for **Render** (backend) and **Vercel** (frontend):

- `backend/Dockerfile` / `backend/Procfile` — respect Render's dynamic `$PORT`
- `backend/app/core/config.py` — accepts a single `DATABASE_URL` (Render's managed Postgres format) or split `POSTGRES_*` vars
- `frontend/vercel.json` — SPA routing rewrite for React Router

Required environment variables (`JWT_SECRET`, `CORS_ORIGINS`, `VITE_API_URL`, etc.) and a full pre-deploy checklist are documented in [`docs/05_INTEGRATION_AND_DEPLOYMENT_READINESS.md`](docs/05_INTEGRATION_AND_DEPLOYMENT_READINESS.md).

## Project structure

```
backend/    FastAPI app, pipeline, integrity subsystem, tests
frontend/   React + TypeScript UI
deploy/     Docker Compose, Kubernetes manifests, nginx config, dev CA
docs/       Full technical documentation (see table above)
sbom/       Signed CycloneDX software bill of materials
verifier/   Standalone offline evidence-bundle verifier (zero app dependency)
```
