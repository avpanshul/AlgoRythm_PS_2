# Updated Overviews — ULPF (Universal Log Pre-processing Framework)

> **Living document.** Update this file after **every prompt / change**.
> How to update:
> 1. Bump `Last Updated` + add row to `Update Log`.
> 2. Update `Current Status`, `Known Issues`, `Next Tasks` if they changed.
> 3. If files/APIs/routes were added/renamed, update the relevant table + `Repo Map`.
> 4. Keep `Verified against` paths accurate (`path:line` style where useful).

- **Project:** ULPF for SIH PS156 — Enterprise SIEM log pre-processing platform
- **Last Updated:** 2026-09-24 (backend running on :8000, degraded — no local Postgres)
- **Last Prompt:** "run it" follow-up — backend start (after pip-install + PGCONNECTTIMEOUT restart)
- **Status snapshot:** Frontend Liquid-Glass redesign built (`npm run build` clean). Backend FastAPI stable in Postgres demo mode. Infra defined in `docker-compose.yml` (10 services) but demo path bypasses Kafka/MinIO/OpenSearch.
- **Prior tracker:** `overall updations.md` (87 lines, still present — this file supersedes it as the detailed source of truth).

---

## 1. What This Project Is

Centralized log ingestion → normalization (ECS-like canonical) → risk scoring → correlation → searchable / auditable SIEM UI.

Pipeline (intended vs current demo reality):

```text
[Intended]
Log Sources → POST /events → Kafka `raw-events` (Redpanda)
  → Raw Vault (MinIO `raw-events` bucket) + Postgres `raw_event_metadata`
  → Worker (`app/workers/main.py`): detect → parse → Drain3/LLM fallback → normalize → correlate (Redis) → risk → OpenSearch `normalized-events`
  → FastAPI reads OpenSearch + Postgres → React UI

[Current demo-active path]
Log Sources → POST /events → local FS (`backend/data/raw_logs/YYYY/MM/DD/*.txt`) + Postgres
  → sync `app/core/processing.py:process_raw_event()` (detect → parse → normalize → PII redact → risk → quality → NormalizedEvent + AuditLog)
  → Postgres only. MinIO/OpenSearch/Kafka init attempted on startup but tolerated as warnings.
```

Evidence:
- Active sync path: `backend/app/core/processing.py`, `backend/app/api/v1/ingestion.py`
- Legacy async path: `backend/app/workers/main.py` (Kafka + MinIO + OpenSearch)
- Startup tolerant init: `backend/app/main.py:27-50`
- Compose infra: `docker-compose.yml`

---

## 2. Tech Stack

| Layer | Tech | Key files / notes |
|---|---|---|
| Backend | FastAPI 0.104.1, Uvicorn, Pydantic 2.5.2 + pydantic-settings | `backend/app/main.py`, `backend/requirements.txt` |
| DB / Migrations | PostgreSQL 15, SQLAlchemy 2.0.23, Alembic 1.12.1, psycopg2 + asyncpg | `backend/app/core/database.py`, `backend/alembic.ini`, `backend/alembic/versions/*.py` |
| Search / Storage / Stream | OpenSearch 2.11.0 + dashboards, MinIO, Redpanda (Kafka-compat `confluent-kafka` 2.3.0), Redis 7 | `backend/app/core/storage.py`, `search.py`, `messaging.py`, `docker-compose.yml` |
| AI/ML | sentence-transformers `all-MiniLM-L6-v2`, Ollama `phi3:mini`, Drain3 0.9.11 | `backend/app/ai/embeddings.py`, `llm.py`, `drain3_engine.py` |
| Auth/Security | PyJWT, passlib[bcrypt], python-jose | `backend/requirements.txt` (no enforced auth middleware yet) |
| Frontend | React 19.2.8, Vite 8.3.0, react-router-dom 7.18.4, TanStack Query 5, axios 1.20, Recharts 3.10, Tailwind 4.3.3, lucide-react 1.47, date-fns, clsx | `frontend/package.json`, `frontend/vite.config.ts`, `frontend/src/api/client.ts` |
| Design | Custom Liquid Glass CSS, Inter + JetBrains Mono | `frontend/src/index.css` (304 lines) |
| Infra | Docker Compose (10 services), Make shortcuts | `docker-compose.yml`, `Makefile`, `backend/Dockerfile`, `frontend/Dockerfile` |
| Tests | pytest (backend only, 1 file), no frontend tests | `backend/tests/unit/test_parsers_risk.py` |

---

## 3. Repo Map

```text
PS156/
  updated overviews.md        <- THIS FILE (living overview)
  overall updations.md        <- legacy status tracker (87 lines)
  README.md                   <- EMPTY (0 bytes, needs rewrite)
  Makefile                    <- up/down/logs/seed/test/lint/format/reset/health
  docker-compose.yml          <- 10 services, net ulp-network
  docker-compose.prod.yml     <- EMPTY
  .env / .env.example         <- Postgres/Kafka/MinIO/OpenSearch/Redis/Ollama/JWT/Risk/Airgapped
  docs/                       <- api.md, architecture.md, schema.md, threat-model.md, deployment.md, demo.md (ALL EMPTY)
  backend/
    Dockerfile, requirements.txt, alembic.ini, gen_migration.py, seed.py
    alembic/env.py, versions/1790093837_initial_migration.py, versions/1790180000_full_stack_tables.py
    datasets/sample/, datasets/synthetic/
    app/main.py               <- FastAPI bootstrap + 16 routers + GET /api/v1/health
    app/core/ config.py, database.py, processing.py (ACTIVE sync pipeline), messaging.py, storage.py, search.py, local_storage.py
    app/models/all.py         <- 16 models, single file
    app/schemas/ canonical.py, events.py
    app/services/mapping_service.py
    app/parsers/ deterministic.py, format_detector.py
    app/normalizers/canonical.py
    app/risk/engine.py
    app/correlation/engine.py
    app/ai/ embeddings.py, llm.py, drain3_engine.py
    app/workers/main.py       <- legacy Kafka worker
    app/api/v1/ ingestion, events, mappings, sources, analytics, analytics_ts, pipeline, dlq, replay, audit, rules, parsers_api, storage_api, admin, integrations_api, threat_intel (16 files, ~54 endpoints)
    app/utils/seed.py         <- legacy MinIO+OpenSearch seed
    tests/unit/test_parsers_risk.py (only real tests); e2e/integration/load dirs empty
    app/audit/, enrichment/, events/, storage/ <- empty placeholders
  frontend/
    Dockerfile (dev server), index.html, package.json, vite.config.ts, tsconfig.*
    src/main.tsx              <- REAL entry (BrowserRouter + QueryClient + AppLayout + Routes)
    src/App.tsx + App.css     <- DEAD Vite boilerplate, not imported
    src/layouts/AppLayout.tsx <- Sidebar (260px) + main (maxWidth 1400)
    src/components/Sidebar.tsx<- glass-panel nav (paths PARTIALLY STALE, see §6)
    src/api/client.ts         <- axios, baseURL VITE_API_URL || localhost:8000/api/v1
    src/types/index.ts        <- CanonicalEvent, RawEvent, Mapping, Source, Stats, RiskSummary, Trace
    src/data/demo.ts          <- DEMO_* fallbacks
    src/pages/ (25 files): Dashboard, EventExplorer, EventDetail, IncidentCenter, LogSources, AddLogSourceWizard, MappingRegistry (ParserLab), MappingReview (Parser Studio), ReplayCenter, FailedEvents (DLQ), RawVault, PrivacyPolicies, DataQuality, PlatformHealth, AuditLogs, UserManagement, DemoJourney, ArchitecturePage, UserFlows, NationalImpact, FeatureClassification + unrouted LiveEvents, UniversalDemo, EventTrace, RiskAnalytics
    src/index.css             <- design system
    public/, dist/, node_modules/
  venv/                       <- local Python env (ignore)
```

---

## 4. Backend — In Detail

### 4.1 Bootstrap — `backend/app/main.py`

- `FastAPI(title=settings.PROJECT_NAME, version=1.0.0, openapi_url=/api/v1/openapi.json)`, CORS `["*"]`.
- `startup_event()`: Alembic `upgrade head` + `init_minio()` + `init_opensearch()`, all try/except print warnings (demo tolerance).
- 16 routers all under `prefix=/api/v1` + `GET /api/v1/health → {status, version, project}` (shallow, not granular — see Next Tasks).

### 4.2 Core — `backend/app/core/`

| File | Purpose |
|---|---|
| `config.py` | `Settings(BaseSettings)`: Postgres URI builder, `KAFKA_BROKERS localhost:9092`, MinIO (`RAW_BUCKET=raw-events`), OpenSearch (`INDEX=normalized-events`), Redis, Ollama (`phi3:mini`), `EMBEDDING_MODEL all-MiniLM-L6-v2`, JWT, `RISK_WEIGHTS {severity .3, action .2, frequency .2, asset .15, correlation .15}`, `CONFIDENCE {auto .90, review .70}`, `AIRGAPPED_MODE=true` |
| `database.py` | `engine (pool_pre_ping)`, `SessionLocal`, `Base`, `get_db()` dependency |
| `processing.py` (340 lines, ACTIVE) | `PII_PATTERNS` (email/Aadhaar/phone/PAN) + `redact_pii()`; `compute_risk_score()` (base 20 + severity/action keywords, thresholds 80/60/40); `normalize_parsed_data()` (CEF/Syslog/JSON/unknown → ECS-ish dict); `process_raw_event()` 9-step sync pipeline → `NormalizedEvent` + `AuditLog`, on fail → `DLQEvent` |
| `messaging.py` | `get_kafka_producer/consumer`, `produce_event()` (confluent_kafka) |
| `storage.py` | `get_minio_client()`, `init_minio()` create bucket |
| `search.py` | `get_opensearch_client()`, `init_opensearch()` mapping for timestamp/event/source/destination/risk |
| `local_storage.py` | Demo FS fallback: `backend/data/raw_logs`, `save/read_raw_log()`, `get_storage_size_bytes/file_count()` |

### 4.3 Models — `backend/app/models/all.py` (16 models)

`Source`, `MappingRegistry` (deterministic/template/semantic/llm/manual + confidence/approved), `UnknownTemplate`, `RawEventMetadata` (`processing_status`), `AuditLog` (user/action/entity/before/after/reason/ip), `NormalizedEvent` (ECS fields + parser/risk/sha/quality/integrity/canonical_json/severity/action + composite `ix_normalized_events_ts_src`), `DLQEvent` (failed/retrying/resolved/assigned + retry counts), `ReplayJob` (pending/running/completed/failed/pending_approval/approved + progress), `Parser` + `ParserVersion` (draft/testing/published/deprecated), `CorrelationRule`, `Role`/`User`/`Organization`, `Integration` (webhook/rest_api/syslog/s3/opensearch), `ThreatIndicator` (ip/domain/hash/url), `PrivacyPolicy`.

Migrations:
- `1790093837_initial_migration.py` (down None): sources, raw_event_metadata, mapping_registry, unknown_templates, audit_logs.
- `1790180000_full_stack_tables.py` (down 1790093837): normalized_events, dlq_events, replay_jobs, parsers, parser_versions, correlation_rules, users, roles, organizations, integrations, threat_indicators, privacy_policies; alters sources/audit_logs.

### 4.4 Parsing / Normalization / Risk / Correlation / AI

- `parsers/format_detector.py:detect_format()` — JSON (try-loads 1.0) / XML (1.0) / CEF: (0.99) / LEEF: (0.99) / `^<\d>` Syslog (0.95) / CSV `,>3 parts` (0.70) / UNKNOWN 0.0.
- `parsers/deterministic.py` — `parse_json/cef/leef/syslog/xml/csv` + `parse_log()` dispatcher. CEF splits `|` + `k=v` regex; Syslog `<PRI>TIME HOST MSG`.
- `normalizers/canonical.py:normalize_event()` — per-field `resolve_field_mapping()`, route `source./destination./event./network.` else `extensions`, int-cast ports, track min-confidence/methods → `CanonicalEvent` (`schemas/canonical.py`).
- `services/mapping_service.py:resolve_field_mapping()` — 1) approved registry → 2) embedding `>=0.90` semantic → 3) LLM `>=0.90` llm → else create unapproved row, return `needs_review`.
- `risk/engine.py:RiskEngine` — weights from settings, `severity_map` + `action_risk_map (deny 30, login_failure 70, malware 100...)`, weighted 0-100, levels 80/60/30.
- `correlation/engine.py:CorrelationEngine` (Redis) — `freq:ip:action` 60s window (>100:100, >20:50, >5:20), `seq:ip` JSON state machine `attack_sequence_1=[port_scan,login_failure,login_success,data_access]` 300s TTL.
- `ai/embeddings.py:EmbeddingEngine` — `all-MiniLM-L6-v2`, 16 canonical fields, `find_best_mapping()` via `1-cosine`.
- `ai/llm.py:LLMReasoner` — Ollama `/api/generate` (`phi3:mini`), `format=json`, validate vs canonical fields, fallback `UNKNOWN 0.0`. Singleton `llm_reasoner`.
- `ai/drain3_engine.py:Drain3Engine` — `TemplateMiner`, `extract_template()`, `get_variables()`. Singleton `drain3_engine`.
- `workers/main.py` (legacy): Kafka `raw-events` poll → MinIO read → detect/parse (Drain3 fallback) → normalize → correlate+risk → OpenSearch index → `processed`.
- `schemas/events.py`: `IngestEventRequest(source_id,raw_log)`, `BatchIngestRequest`, `RawEventResponse`.

### 4.5 API — 16 routers, ~54 endpoints (`prefix /api/v1`)

| Router | Endpoints |
|---|---|
| `ingestion.py` | `POST /events` (single), `POST /events/batch`, `POST /ingest/syslog` (raw body). Helper creates `evt_*` uuid + sha256 + `YYYY/MM/DD/*.txt` + `RawEventMetadata(processing)` then sync `process_raw_event()` |
| `events.py` | `GET /events?q,severity,risk_level,page,size → {total,page,size,events}`, `GET /events/{id}`, `GET /events/{id}/raw`, `GET /events/{id}/trace` (6-stage provenance), `POST /reprocess/{id}` |
| `mappings.py` | `GET /mappings?approved,needs_review`, `POST /mappings/{id}/approve`, `POST /mappings/{id}/reject` (+Audit) |
| `sources.py` | `GET /sources`, `POST /sources` |
| `analytics.py` | `GET /risk` (distribution/avg/max/critical[5]), `GET /stats` (total/formats/severities/top_actions[10]/24h hourly) |
| `analytics_ts.py` | `GET /analytics/timeseries?start,end,interval,source_id` (normalized+DLQ buckets + failures_by_reason) |
| `pipeline.py` | `GET /pipeline/health` (rates/lag/parse rates/dlq/latency 45ms/storage/quality/stages[7]) |
| `dlq.py` | `GET /dlq?status,reason,source_id,page,size`, `POST /dlq/{id}/retry`, `/resolve`, `/assign` |
| `replay.py` | `GET /replay/jobs`, `POST /replay/jobs`, `GET /replay/jobs/{id}`, `POST /replay/jobs/{id}/approve?approved_by` |
| `audit.py` | `GET /audit-logs?user,action,entity_type,q,page,size` |
| `rules.py` | `GET/POST /rules`, `GET/PUT/DELETE /rules/{id}` (+Audit) |
| `parsers_api.py` | `GET/POST /parsers`, `GET/PUT /parsers/{id}`, `POST /parsers/{id}/test` (parse+normalize+redact), `POST /parsers/{id}/publish` (snapshot version, bump patch), `GET /parsers/{id}/versions` |
| `storage_api.py` | `GET /storage/summary` (counts, local FS bytes, `backend:local_filesystem`) |
| `admin.py` | `GET/POST /users`, `PUT/DELETE /users/{id}`, `GET /roles`, `GET /organizations`, `GET /connectors` (stub c1 Kafka/c2 Syslog/c3 S3) |
| `integrations_api.py` | `GET/POST /integrations`, `PUT/DELETE /integrations/{id}`, `POST /integrations/{id}/test` (latency 42ms) |
| `threat_intel.py` | `GET/POST /threat-intel/indicators`, `POST /threat-intel/check` (match + hits/last_seen bump) |
| root | `GET /health` (shallow) |

### 4.6 Seeds, Tests, Helpers

- `backend/seed.py` (demo Postgres-only, 176 lines): orgs (MEITY/CERT/NIC), roles+users (admin/analyst/dev), sources (FW-001/SYS-LNX/WEB-01/EDR-01), parsers (nginx/syslog), 100 NormalizedEvent + RawEventMetadata (every 5th denied/high/75 else allowed/low/10), 5 DLQ, rules (Brute Force/Data Exfil), intel (C2 IP/evil-domain), integrations (Splunk/Slack).
- `backend/app/utils/seed.py` (legacy full-stack): MinIO+OpenSearch seed, 8 synthetic logs (SSH deny in Syslog/CEF/JSON/UNKNOWN + login sequences), risk map LOW 20/MED 45/HIGH 72/CRIT 91.
- `backend/gen_migration.py`: SQLite-memory autogenerate helper.
- Tests: only `backend/tests/unit/test_parsers_risk.py` (format detector 6 cases, CEF/Syslog/JSON parsers, RiskEngine high/low). `e2e/integration/load` empty.

---

## 5. Frontend — In Detail

### 5.1 Entry / Layout

- `src/main.tsx`: `BrowserRouter + QueryClient(retry:1) + AppLayout + Routes` (22 routes + 2 placeholders). Imports `index.css`.
- `src/layouts/AppLayout.tsx`: flex 100vh, `Sidebar` 260px + `main (flex:1, pad 32x40, maxW 1400)`.
- `src/App.tsx` = dead boilerplate (counter/hero), not imported. `src/App.css` likewise dead.

### 5.2 Routes (`src/main.tsx:47-74`) vs Sidebar (`src/components/Sidebar.tsx`)

Real routes: `/, /events, /events/:id, /incidents, /sources, /add-source, /parsers, /parser-studio, /replay, /dlq, /raw, /privacy, /data-quality, /health, /audit, /users, /integrations (placeholder), /docs (placeholder), /demo, /architecture, /user-flows, /national-impact, /features`.

Sidebar links that have **NO matching route** (stale): `/integrity, /analytics, /storage, /admin, /integrations/siem, /integrations/ti`. Sidebar labels: Dashboard, Log Explorer, Data Sources, Parser Lab, Integrity & Replay, Analytics & Alerts, Storage, Administration + Integrations (SIEM, Threat Intel). Footer: Admin User / SOC Analyst, System Healthy, v1.0.0.

### 5.3 Pages (25 files in `src/pages/`)

| Route | Page | API wired? | Notes |
|---|---|---|---|
| `/` | `Dashboard.tsx` | `GET /stats`, `GET /pipeline/health` | KPIs + Recharts Area/Pie; `DEMO_*` + random timeline fallback |
| `/events` | `EventExplorer.tsx` | `GET /events?q=` | Table + filter UI; `DEMO_EVENTS` fallback |
| `/events/:id` | `EventDetail.tsx` | `GET /events/{id}`, `GET /events/{id}/trace` (catch→null) | Tabs Raw/Normalized/Redacted/Provenance; hardcoded SAMPLE blocks |
| `/incidents` | `IncidentCenter.tsx` | none | Mock-only |
| `/sources` | `LogSources.tsx` | `GET /sources` | Admin onboarding; `DEMO_SOURCES` fallback |
| `/add-source` | `AddLogSourceWizard.tsx` | none | Mock wizard |
| `/parsers` | `MappingRegistry.tsx` (ParserLab) | none (doc claims `GET /mappings`) | Hardcoded RAW_SAMPLE+YAML+MAPPINGS |
| `/parser-studio` | `MappingReview.tsx` | none | Mock review |
| `/replay` | `ReplayCenter.tsx` | `GET /replay/jobs`, `GET /dlq`, `GET /audit-logs`, `POST /dlq/{id}/retry` | Verify+replay+DLQ tabs |
| `/dlq` | `FailedEvents.tsx` | none (client has `getDlq`) | Mock |
| `/raw` | `RawVault.tsx` | none | Mock |
| `/privacy` | `PrivacyPolicies.tsx` | none | Mock |
| `/data-quality` | `DataQuality.tsx` | none | Mock |
| `/health` | `PlatformHealth.tsx` | none (client has `checkHealth/getPipelineHealth`) | Mock |
| `/audit` | `AuditLogs.tsx` | none (client has `getAuditLogs`) | Mock |
| `/users` | `UserManagement.tsx` | none (client has `getUsers`) | Mock |
| `/demo, /architecture, /user-flows, /national-impact, /features` | DemoJourney, ArchitecturePage, UserFlows, NationalImpact, FeatureClassification | none | Static/marketing |
| (unrouted) | `LiveEvents.tsx` | `POST /events` mutation | Manual ingest form |
| (unrouted) | `UniversalDemo.tsx` | `POST /events` loop + `GET /events/{id}` | Staged demo |
| (unrouted) | `EventTrace.tsx` | **BROKEN `api.traceEvent()` (should be `getEventTrace`)** | Provenance timeline |
| (unrouted) | `RiskAnalytics.tsx` (`AnalyticsAndAlerts`) | none (constants `QUALITY/TREND/FAILURE/RULES`) | Intended `GET /risk`, `/analytics/timeseries`, `/rules` unused |

Only ~7/25 pages actually call the backend; rest are mock/static.

### 5.4 API Client — `src/api/client.ts`

Axios `baseURL = VITE_API_URL || http://localhost:8000/api/v1`. Methods: health/pipeline, ingest/batch/events/trace/reprocess, DLQ (get/retry/resolve), replay (get/create/approve), audit, stats/risk/timeseries/rules CRUD, parsers (get/test/publish), storage summary, users/roles/orgs, integrations + TI, legacy sources/mappings/auto. Note: `docker-compose.yml` sets `VITE_API_URL=http://localhost:8000` (missing `/api/v1` suffix) — mismatch vs client default.

### 5.5 Types / Demo Data / Config

- `src/types/index.ts`: `CanonicalEvent`, `RawEvent`, `Mapping`, `Source`, `Stats`, `RiskSummary`, `TraceStage/EventTrace`.
- `src/data/demo.ts`: `DEMO_SOURCES[8]`, `DEMO_EVENTS[5]`, `DEMO_ALERTS[4]`, `DEMO_PIPELINE_STAGES[7]`, `DEMO_DLQ_FAILURES[4]`, `DEMO_REPLAY_JOBS[3]`.
- `vite.config.ts`: `tailwindcss() + react()` only (no proxy/alias/tests). `index.html`: `#root + /src/main.tsx`. `frontend/Dockerfile`: dev server (`npm run dev --host 0.0.0.0`), not prod build.

### 5.6 Design System — `src/index.css` (Liquid Glass, 304 lines)

- Fonts: Inter 400/500/600/700 + JetBrains Mono 400/500/700. Body Inter, `.mono` code.
- Tokens: `bg-base #f0f4f8`, `primary #1e40af / light #3b82f6`, `secondary #0d9488`, `success #10b981`, `warning #f59e0b`, `danger #ef4444`, `ai #8b5cf6`; text `main #0f172a / muted #475569 / light #94a3b8`; glass `bg 65% white / hover 85%`, blur `18px saturate 120%`, shadows blue-tinted.
- Body: layered radial (sky/teal/indigo) + linear `#f8fafc→#f1f5f9`.
- Primitives: `.glass-panel/.glass-card (hover lift -2px)/.glass-floating/.nav-item[.active]/.badge[-success|-warning|-danger|-primary|-neutral|-ai]/.glass-table/.glass-input/.code-block/.btn[-primary|-secondary|-ghost]/.page-title/.page-subtitle/.animate-fade-in`, 6px scrollbar.

---

## 6. Infra / Config / Ops

`docker-compose.yml` (v3.8, `ulp-network`, 10 services): postgres:15-alpine (5432, healthy), minio (9000/9001), opensearch 2.11.0 (9200/9600, single-node, security off, 512m) + dashboards (5601), redis:7 (6379), redpanda (9092/29092, PLAINTEXT redpanda:29092 / OUTSIDE localhost:9092), ollama (11434), backend (8000, `uvicorn --reload`, depends postgres/minio healthy + redpanda/opensearch/redis), worker (`python -m app.workers.main`), frontend (5173, `npm run dev --host 0.0.0.0`).

`.env`: Postgres `postgres:5432/ulp_db`, Kafka `redpanda:29092`, MinIO `minio:9000/admin/password123`, OpenSearch `http://opensearch:9200`, Redis `redis://redis:6379/0`, Ollama `http://ollama:11434/phi3:mini`, JWT `super-secret-change-in-prod`, risk/confidence weights, `AIRGAPPED_MODE=true`.

`Makefile`: `up/down(-v)/logs/seed (app.utils.seed)/test (pytest)/lint (flake8)/format (black)/reset/health (curl /api/v1/health | jq)`.

---

## 7. Current Status / Gaps / Next

**Working:** ingestion (single/batch/syslog) → sync normalize → Postgres; events search/detail/trace/reprocess; stats/risk analytics; DLQ retry/resolve/assign; replay CRUD/approve; audit/rules/parsers/storage/admin/integrations/TI APIs; Dashboard/Explorer/Detail/Sources/Replay wired to live APIs; clean frontend build.

**Partial / Mock:** `GET /mappings` approve flow exists but Parser Lab page uses hardcoded data; Analytics secondary charts mock; 18/25 frontend pages mock-only; Sidebar routes stale; `EventTrace.tsx` calls nonexistent `api.traceEvent`; `VITE_API_URL` missing `/api/v1` in compose; `GET /health` shallow; no API-timeout handling.

**Docs debt:** `README.md`, `docker-compose.prod.yml`, all `docs/*.md` empty.

**Next Tasks:**
1. Granular `GET /health` (DB/Kafka/MinIO/OpenSearch/Redis checks).
2. Wire Parser Lab + Analytics + DLQ + Audit + Users + Health pages to existing client methods; fix `traceEvent` → `getEventTrace`; align Sidebar paths to `main.tsx` routes; remove dead `App.tsx`.
3. Parser Lab publish E2E test; add integration/e2e/load tests (dirs empty); fix compose `VITE_API_URL` to include `/api/v1`; add frontend tests/lint; fill `docs/` + `README.md`; decide Kafka vs sync pipeline as canonical (worker vs `processing.py` duplication).

---

## 9. Requirements Gap List (from `Universal Log Pre.docx` + `Presentation1.pptx`)

Source: PS docx §2 (mandatory), §3–4 (proposed/novelty), pptx 9-feature table. Verified against code 2026-09-24.

### A. Mandatory baseline (docx §2)

| # | Requirement | Status | Notes |
|---|---|---|---|
| 1 | Multi-source ingestion (FW/IDS/proxy/web/server) | Done | `POST /events`, `/batch`, `/ingest/syslog`; wizard UI mock |
| 2 | Multi-format (Syslog/JSON/XML/CSV/CEF/plaintext) | Done | 6 deterministic parsers + UNKNOWN |
| 3 | Lossless raw storage + forensic retrieval | Partial | Local-FS demo + raw API real; MinIO path legacy/unverified |
| 4 | Parsing + field extraction | Done | `parsers/deterministic.py`, tested |
| 5 | ECS-like normalization | Done | + mapping service (registry→embedding→LLM) |
| 6 | Traceability raw↔normalized | Done | `GET /events/{id}/trace` + UI (no `/lineage` alias) |
| 7 | Extensibility (new sources w/o core change) | Partial | Parser CRUD/test/publish real; onboarding + auto-suggest UI mock |
| 8 | Scale/perf proof, SIEM/data-lake feeds | Missing | No load tests; Kafka path inactive; Splunk/Slack rows only, no working export |

### B. Proposed high-value (docx §3 / pptx 1–8)

| # | Feature | Status | What's left |
|---|---|---|---|
| 1 | Integrity: SHA-256 + batch chain + `/verify` | Partial | Per-event hash real; **no batch/Merkle chain, no `/verify` API** (Verify button is client-side only) |
| 2 | Redaction: vault vs analytics view, policies | Partial | Engine real (Aadhaar/PAN/phone/email); **no privacy-policy API router** (model exists, UI mock) |
| 3 | Parser marketplace + auto-mapping + approval | Partial | Registry/test/publish real; **sample→suggest→approve flow mock** |
| 4 | Anomaly score + 1–2 correlation rules | Partial | Engine + rules CRUD + 2 seeded rules real; UI mock |
| 5 | Provenance/lineage metadata | Done | Via `/trace`; add `/lineage` alias for PS wording |
| 6 | Data-quality scoring (pptx 5) | Partial | `quality_score` computed + in stats; **no quality filter on `/events`**, UI mock |
| 7 | Self-monitoring dashboard (pptx 7) | Partial | `/pipeline/health` real; page mock; no Prometheus/Grafana |
| 8 | Cross-org correlation tokens (pptx 8) | Missing | No HMAC/token design, vault, or API |

### C. Novelty / roadmap (docx §4 / pptx 9)

| # | Feature | Status |
|---|---|---|
| 1 | Tiered storage + sampling | Missing (storage summary is a stub) |
| 2 | Ledger anchoring of batch roots | Missing (optional/demo — needs batch chain first) |
| 3 | Threat-intel enrichment | Partial (manual indicators + `/check`; no feeds, no auto-enrich at ingest) |
| 4 | ML-assisted parser generation | Partial (LLM field fallback real; full sample→parser flow = roadmap) |

### D. Engineering leftovers

- Frontend: `LiveEvents`/`RiskAnalytics` unrouted; ~10 pages mock-only (wired: Dashboard, Explorer, Detail, Sources, Replay, DLQ-via-Replay); static demo pages untouched; 935KB chunk (code-split recharts).
- Backend: no auth enforcement; shallow `/health`; compose `VITE_API_URL` missing `/api/v1` suffix.
- Docs: `README.md`, `docs/*.md`, `docker-compose.prod.yml` empty.
- Tests: 1 unit file only; e2e/integration/load dirs empty.
- Ops (this machine): no Docker; no local Postgres/Redis/Kafka/MinIO/OpenSearch — backend runs degraded on demo fallbacks.

---

## 8. Update Log (append after every prompt)

| ID | Date | Prompt / Change summary | Files touched | Tests |
|---|---|---|---|---|
| 001 | 2026-09-23 | Terminal → Enterprise UI plan; init `overall updations.md` | `overall updations.md` | Pending UI overhaul |
| 002 | 2026-09-23 | Liquid Glass redesign (index.css, Dashboard, Sidebar, Explorer/Detail, Sources, Parser Lab, Replay, Analytics) | `src/index.css`, `layouts/AppLayout.tsx`, `components/Sidebar.tsx`, `pages/*.tsx` | `npm run build` clean |
| 003 | 2026-09-24 | Created living `updated overviews.md` (full backend/frontend/infra/API audit; verified main.tsx, main.py, client.ts) | `updated overviews.md` | Read-verified; no code change |
| 004 | 2026-09-24 | Fixed frontend build errors + white-theme redesign: `npm install` (tsc missing); rewrote `index.css` flat white (no glass/gradients, added `--color-text-primary/--color-bg-primary/--color-border` aliases + `.cyber-input/.json-viewer/.btn-primary/.pulse-dot` compat); fixed Sidebar routes to real paths (`/replay,/data-quality,/raw,/users,/integrations,/health`); fixed `EventTrace api.traceEvent→getEventTrace`; fixed double-unwrap `api.getStats/getEvents/getEventTrace .then(r=>r.data)`; rewrote Dashboard as flat stats row + plain tables; fixed `main.tsx` placeholder color var | `frontend/src/index.css`, `components/Sidebar.tsx`, `layouts/AppLayout.tsx`, `pages/Dashboard.tsx`, `pages/EventTrace.tsx`, `pages/EventExplorer.tsx`, `pages/EventDetail.tsx`, `main.tsx` | `npx tsc -b` clean; `npx vite build` success (only >500kB chunk warning) |
| 005 | 2026-09-24 | Continued de-boxing: EventExplorer (removed filter box + quality bars, plain toolbar + count line), LogSources (4 summary boxes → plain stat row, removed icon tiles/glow dots), EventDetail (pill tabs → underline tabs, glass sections → bordered sections, provenance timeline → plain table, risk bars → table), EventTrace (timeline cards → plain stage table) | `pages/EventExplorer.tsx`, `pages/LogSources.tsx`, `pages/EventDetail.tsx`, `pages/EventTrace.tsx` | `npx tsc -b` clean; `npx vite build` success (only chunk warning) |
| 006 | 2026-09-24 | Batch 3: global CSS aliases (`.data-table`→`glass-table` styles, `.badge-low/info/medium/high/critical` — fixes unstyled tables/badges in Audit/DF/Incidents/DLQ/Wizard/Architecture); DataQuality + AuditLogs + FailedEvents + IncidentCenter + ReplayCenter + MappingRegistry (Parser Lab) flattened to header-row + stat-row + plain tables, pill tabs → underline tabs, step pills → numbered breadcrumb | `src/index.css`, `pages/DataQuality.tsx`, `pages/AuditLogs.tsx`, `pages/FailedEvents.tsx`, `pages/IncidentCenter.tsx`, `pages/ReplayCenter.tsx`, `pages/MappingRegistry.tsx` | `npx tsc -b` clean; `npx vite build` success (only chunk warning) |
| 007 | 2026-09-24 | Batch 4: PlatformHealth (4 service boxes → stat row), UserManagement (header box → row, role badges → badge-primary, roles card → bordered panel), RawVault (header box → row, detail card → bordered panel), PrivacyPolicies (3 stat boxes → stat row, policy cards → single table), MappingReview/Parser Studio (full rewrite: header row + 3 bordered panes), AddLogSourceWizard (header box → row, stepper pills → underline breadcrumb, content box → bordered panel); added `--color-bg-secondary` alias | `pages/PlatformHealth.tsx`, `pages/UserManagement.tsx`, `pages/RawVault.tsx`, `pages/PrivacyPolicies.tsx`, `pages/MappingReview.tsx`, `pages/AddLogSourceWizard.tsx`, `src/index.css` | `npx tsc -b` clean; `npx vite build` success (only chunk warning) |
| <!-- 004 | YYYY-MM-DD | <prompt summary> | <files> | <tests> --> | | | |
| 008 | 2026-09-24 | Backend started separately: installed missing sys-python deps (pyyaml, minio, opensearch-py, redis, ollama, PyJWT, passlib, python-jose, drain3, confluent-kafka); fixed 60s+ startup hang with PGCONNECTTIMEOUT=5 (no local Postgres/Docker on machine); /health healthy, openapi loads, /stats degrades gracefully | system python env (no repo change) | /api/v1/health 200; /api/v1/stats graceful error JSON |

### Current Context Summary (refresh each update)

UI is Liquid-Glass enterprise SIEM on white/light-gray; Dashboard driven by live `GET /stats` (+ pipeline health); Explorer/Detail trace Raw→Risk; backend is FastAPI + Postgres demo-sync pipeline (Kafka/MinIO/OpenSearch present in compose but bypassed); AI mapping (embeddings + Ollama phi3:mini + Drain3) exists but only fully exercised via legacy worker path; ~54 endpoints across 16 routers; frontend has 25 pages but only ~7 call APIs; docs/README still empty.
