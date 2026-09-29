# 02 — System Architecture

> Cross-references: [`01_PROJECT_OVERVIEW.md`](01_PROJECT_OVERVIEW.md) (what/why/status), [`03_FEATURES_TECH_STACK_AND_DATA.md`](03_FEATURES_TECH_STACK_AND_DATA.md) (full feature/tech inventory), [`05_INTEGRATION_AND_DEPLOYMENT_READINESS.md`](05_INTEGRATION_AND_DEPLOYMENT_READINESS.md) (deployment topology, ports, env vars).

## 1. Complete system architecture

```text
                         +-------------------------------------------------+
                         |                  Log sources                    |
                         |  HTTP POST /events, /events/batch,               |
                         |  /ingest/syslog, /ingest/windows-event-log       |
                         |  or standalone UDP/TCP/mTLS syslog listener      |
                         |  (app/workers/syslog_listener.py, its own        |
                         |  process, ports 5514 plaintext / 6514 mTLS)      |
                         +--------------------------+-----------------------+
                                                    |
                                                    v
+----------------------------------------------------------------------------------+
|  FastAPI backend  (backend/app, 153 routes / 30 routers / 34 models)             |
|                                                                                    |
|  Ingestion (api/v1/ingestion.py) --sync (default) or --kafka (INGEST_BACKEND)-->  |
|      v                                                                            |
|  Raw vault (core/local_storage.py) -- gzip + optional Fernet encryption,          |
|      local filesystem by default, MinIO wired as the optional object-store path  |
|      v                                                                            |
|  Processing pipeline (core/processing.py:process_raw_event) -- see section 3      |
|      v                              \                                             |
|  NormalizedEvent (SQLite/Postgres)   \-- on failure: DLQEvent + Drain3 cluster    |
|  + MerkleLeaf + Checkpoint rows           (UnknownTemplate)                       |
|      v                                                                            |
|  Background daemon threads:                                                       |
|    - live_detection.py (30s: correlation + Sentinel, auto-opens Cases)            |
|    - checkpoint_scheduler.py (optional, timer-based checkpoint batching)          |
|    - auto_ingest.py (optional, scheduled re-ingestion of a real corpus)           |
|      v                                                                            |
|  ~30 API routers (api/v1/*) -- auth, events, sources, parsers, mappings,          |
|  pack_sharing, unknown_clusters, dlq, replay, integrity, evidence, export,        |
|  correlations, entities, cases, graph, hunts, retention, privacy_policies,        |
|  supervisory, admin, integrations_api, settings_api, sparks, threat_intel, ...    |
+-----------------------------------+------------------------------------------------+
                                    |  JWT bearer auth (+ optional MFA preauth step)
                                    v
+----------------------------------------------------------------------------------+
|  React 19 + TypeScript + Vite frontend (frontend/src, 29 pages, 26 routes)        |
|  TanStack Query for data fetching, axios client (api/client.ts), react-router-dom |
+----------------------------------------------------------------------------------+
```

Optional production-scale infrastructure (`docker-compose.yml`): PostgreSQL, MinIO, OpenSearch(+Dashboards), Redis, Redpanda (Kafka-API-compatible), Ollama. See [`05_INTEGRATION_AND_DEPLOYMENT_READINESS.md`](05_INTEGRATION_AND_DEPLOYMENT_READINESS.md) for exactly which of these paths are live-verified versus documented-only.

## 2. Backend architecture (`backend/app/`)

Directory responsibilities, verified by direct inspection:

| Directory | Responsibility |
|---|---|
| `api/v1/` | 30 FastAPI routers (full list: §5). One file per resource area. |
| `core/` | `config.py` (`Settings`, ~90 env-driven fields, verified by direct read), `database.py`, `deps.py` (`get_current_user`/`require_role`/`get_ingest_or_user`), `security.py` (password hashing, JWT, TOTP MFA), `security_middleware.py` (headers, rate limiting), `local_storage.py` (raw vault), `vault_encryption.py` (Fernet), `processing.py` (the pipeline itself), `retention.py`. |
| `models/` | `all.py` — all 34 SQLAlchemy models in one file (full list: §4). |
| `parsers/` | `format_detector.py` (13-format heuristic cascade), `deterministic.py` (per-format structural parsers), `mapping_engine.py` (source-pack YAML executor), `sandbox.py` (isolated-process fixture testing). |
| `normalizers/` | `ocsf.py` — best-effort OCSF 1.x mapping, explicitly not a compliance claim. |
| `ai/` | `llm.py` (Ollama field-mapping classifier), `embeddings.py` (semantic similarity), `drain3_engine.py` (unknown-template clustering), `sentinel.py` (entity behavioral profiling), `event_classifier.py` (built, **not integrated** — see doc 01 §9), `triage_bandit.py` (LinUCB alert-triage, offline-validated, **not in production**). |
| `services/` | `pack_drafting.py` (agentic pack drafting), `mapping_service.py`, `live_detection.py` (30s background loop), `spark_detection.py`, `auto_reparse.py`, `auto_ingest.py`. |
| `analytics/` | `correlation.py` (+ `correlation_rules/*.yaml`), `detection.py` (silent-source/volume-anomaly), `drift.py` (source fingerprint drift), `epistemic.py`, `graph.py` (entity graph/attack-path/timeline). |
| `integrity/` | `merkle.py`, `signing.py` (Ed25519 file or PKCS#11/HSM), `canonical_json.py` (RFC 8785), `service.py`, `witness.py` (multi-party cosigning), `rfc3161.py` (trusted timestamping). |
| `notifications/` | `engine.py` (severity-tiered notify/escalate), `channels.py` (SMS via generic HTTP gateway — inert/`not_configured` unless a real gateway URL is set). |
| `workers/` | `syslog_listener.py` (standalone UDP/TCP/mTLS process), `main.py` (Kafka consumer, the async `INGEST_BACKEND=kafka` path), `checkpoint_scheduler.py`. |
| `schemas/` | Pydantic request/response models. |
| `correlation/`, `risk/` | Contain `engine.py` files **not imported anywhere else in the codebase** (verified via grep in this audit) — dead code, superseded by `app/analytics/correlation.py` and `compute_risk_score()` in `processing.py`. |

## 3. Data flow: raw log → canonical event

`app/core/processing.py:process_raw_event`, verified stage-by-stage by direct read:

1. **Format detection** (`format_detector.py:detect_format`) — ordered cascade, first match wins: JSON → XML → CEF → LEEF → Syslog (RFC 3164/5424, with and without a `<PRI>` header) → HDFS/Hadoop daemon log → Log4j-pattern (Hadoop YARN / Zookeeper) → BlueGene/L (BGL) RAS event → a second HPC node-event shape → Apache httpd error log → Windows CBS/trace log → CSV (heuristic) → KeyValue (heuristic) → `UNKNOWN`.
2. **Parsing** (`deterministic.py:parse_log`) — format-specific structural parser, no LLM involved.
3. **Normalization** — a published **source pack** (YAML field-mapping, `mapping_engine.py:apply_source_pack`) if the format+vendor combination has one, else a hardcoded per-format mapper (`normalize_parsed_data`). Both preserve unmapped fields.
4. **PII redaction** (`redact_pii`) — email, Aadhaar-shaped, Indian-mobile-shaped, PAN-shaped patterns.
5. **Event timestamp extraction** — the log's own timestamp field if one is recognizable, else ingestion time, with `normalization.timestamp_source` recording which.
6. **Risk scoring** (`compute_risk_score`) — base + severity + action-keyword + a large-transfer heuristic, capped at 100, compared against the source's own 50-event rolling baseline.
7. **Quality/epistemic classification** (`app/analytics/epistemic.py`).
8. **Canonical JSON assembly** — ECS-like `event`/`source`/`destination`/`network`/`user`/`device` blocks plus a best-effort OCSF mapping and the `unmapped` leftovers.
9. **Integrity hash** — RFC 8785 canonicalization, then SHA-256.
10. **Persistence** — `NormalizedEvent` row + a Merkle leaf append, same transaction.
11. **Checkpoint** — if `AUTO_CHECKPOINT_EVERY_EVENT` (default true), a fresh signed checkpoint is issued immediately (O(n) per call — see benchmarks in doc 04).
12. **Audit log entry.**
13. **On any exception** in the above — a `DLQEvent` row instead, with `failure_reason`/`failure_detail`, and (for unknown-format failures) a Drain3 `drain_cluster_id`.

Downstream, on already-stored `NormalizedEvent` rows (not inline during ingestion): the correlation engine, Sentinel entity-behavior profiling, and the 30-second `live_detection.py` background cycle that ties both together and auto-opens cases.

## 4. Database / storage architecture

- **Primary store**: PostgreSQL 15 (`docker-compose.yml` default) or SQLite (`backend/scripts/run_local_demo.py`, what this audit's live numbers were measured against). 34 ORM models in `app/models/all.py`, confirmed by direct count: `Source`, `MappingRegistry`, `UnknownTemplate`, `RawEventMetadata`, `PlatformSetting`, `AuditLog`, `NormalizedEvent`, `DLQEvent`, `MerkleLeaf`, `Checkpoint`, `ReplayJob`, `Parser`, `ParserVersion`, `Case`, `RetentionPolicy`, `SourceFingerprint`, `SavedQuery`, `LegalHold`, `OnCallContact`, `Notification`, `EntityProfile`, `CorrelatedIncident`, `AgentReasoningTraceEntry`, `Spark`, `CorrelationRule`, `Role`, `User`, `IngestToken`, `IngestionRun`, `Organization`, `Integration`, `ThreatIndicator`, `PrivacyPolicy`, `NormalizedEventVersion`.
- **Raw vault**: local filesystem (`backend/data/raw_logs/`), gzip-compressed, optionally Fernet-encrypted (`VAULT_ENCRYPTION_KEY`). MinIO is wired as the alternate object-store backend but is not in the live-verified local path.
- **Migrations**: Alembic (`backend/alembic/`) targets PostgreSQL; the local SQLite path bypasses Alembic entirely (`Base.metadata.create_all()`), confirmed by reading `run_local_demo.py` — meaning **Alembic migrations are only actually exercised against a real Postgres**, which per `docs`-history happened once, during the live Kubernetes smoke test (found and fixed a real duplicate-index migration bug at that time).

## 5. All API routers (30, directly enumerated from `app/main.py`)

| Router | Tag | Router-level auth |
|---|---|---|
| `auth.py` | Auth | — (login itself is necessarily open) |
| `ingestion.py` | Ingestion | `get_ingest_or_user` (accepts either a user session or a scoped `IngestToken`) |
| `events.py` | Events | open |
| `mappings.py` | Mappings | open (specific approve/reject actions require auth) |
| `sources.py` | Sources | open |
| `analytics.py` | Analytics | open |
| `pipeline.py` | Pipeline | open |
| `dlq.py` | DLQ | required |
| `replay.py` | Replay | open (approval action requires auth) |
| `audit.py` | Audit | required |
| `analytics_ts.py` | Analytics TS | open |
| `rules.py` | Rules | required |
| `parsers_api.py` | Parsers | required |
| `storage_api.py` | Storage | open |
| `admin.py` | Admin | required |
| `integrations_api.py` | Integrations | required |
| `settings_api.py` | Settings | open |
| `threat_intel.py` | Threat Intel | open |
| `integrity.py` | Integrity | open |
| `supervisory.py` | Supervisory | open |
| `evidence.py` | Evidence | open |
| `export.py` | Export | open |
| `privacy_policies.py` | Privacy | required |
| `correlations.py` | Correlation | open |
| `entities.py` | Entities | open |
| `cases.py` | Cases | open |
| `retention.py` | Retention | open |
| `graph.py` | Graph | open |
| `hunts.py` | Hunts | open |
| `unknown_clusters.py` | Unknown Clusters | required |
| `pack_sharing.py` | Pack Sharing | required |
| `sparks.py` | Sparks | open |

**Note, verified by direct read of `app/main.py`**: "open" here means no router-level `Depends(get_current_user)` is applied at `include_router()`. Several of these routers still enforce auth per-route internally (e.g. `mappings.py`'s approve/reject, `replay.py`'s approval action, several `settings_api.py`/`cases.py` write actions call `get_current_user` as a route-level dependency even though the router itself isn't blanket-protected). A full per-route audit of exactly which of the "open" routers' individual write endpoints are actually unauthenticated was not exhaustively completed in this pass — flagged as a follow-up in [`05_INTEGRATION_AND_DEPLOYMENT_READINESS.md`](05_INTEGRATION_AND_DEPLOYMENT_READINESS.md).

Total: **153 routes registered** (measured by directly importing `app.main` and counting `app.routes` in this audit — includes FastAPI/Starlette's own internal docs/openapi/static routes, not just this project's ~130 API endpoints). The live, authoritative, always-current reference for exact request/response shapes is the running server's own Swagger UI at `/docs`.

## 6. Frontend architecture (`frontend/src/`)

| Directory | Contents |
|---|---|
| `pages/` | 29 files, one per route (26 are actually wired into `main.tsx`; `ParserLab.tsx` was confirmed unreferenced/dead in prior audits — not re-verified byte-for-byte in this pass). |
| `api/client.ts` | Single axios instance + one `api` object with every backend call as a named method; attaches the bearer token, redirects to `/login` on 401. |
| `auth/` | `authStore.ts` (localStorage token), `RequireAuth.tsx` (route guard). |
| `layouts/AppLayout.tsx` | Shared shell (sidebar/nav) wrapping every authenticated page. |
| `components/`, `charts/`, `hooks/`, `types/`, `utils/` | Shared UI, Recharts wrappers, custom hooks, TS types, formatting helpers. |

Auth model: `Login.tsx` → `POST /auth/login` (or the MFA-preauth flow if `mfa_required` comes back) → token stored → every protected route wrapped in `<RequireAuth>`. TanStack Query (`retry: 1` globally, several pages override this per-query) handles fetching/caching.

## 7. Security architecture

Detailed compliance/threat-model mapping lives in the project's compliance materials; this section states what the code implements, verified by direct read this session:

- **Authentication**: JWT bearer (`PyJWT`, HS256 default), bcrypt password hashing (`passlib`).
- **MFA**: real TOTP (`pyotp`), a preauth-token flow (`MfaVerifyRequest`/`preauth_token`) gating a real session token behind a 6-8 digit code once enabled per-account.
- **Account lockout**: real, in `app/api/v1/auth.py:_authenticate` — `locked_until` is checked before the password comparison (so a locked account can't be brute-forced during its own lockout window), failed attempts increment and cross `ACCOUNT_LOCKOUT_THRESHOLD` (default 5) into a `ACCOUNT_LOCKOUT_MINUTES` (default 15) lock, logged to `AuditLog`.
- **Separate ingest-vs-admin token identities**: real — `IngestToken` model, `POST/GET/DELETE /admin/ingest-tokens`, `get_ingest_or_user` dependency on the ingestion router accepts either.
- **RBAC**: `Role`/`User`/`Organization` models; `require_role()` dependency exists and is used at specific enforcement points (e.g. parser-publish separation of duties — a parser's author cannot publish their own parser).
- **Audit log**: hash-chained (`AuditLog`'s SQLAlchemy `before_insert` listener), `GET /audit-logs/verify` re-walks the chain.
- **Web hardening**: CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, HSTS-when-HTTPS, a dependency-free per-client rate limiter (`app/core/security_middleware.py`), explicit CORS allowlist (never a wildcard).
- **Integrity**: see doc 01 §7-8 and the dedicated security/compliance material — Merkle tree, signed checkpoints, HSM option, mTLS, RFC 3161, witnessing.
- **Encryption at rest**: Fernet for the raw vault (`VAULT_ENCRYPTION_KEY`) and for specific sensitive DB columns (`DB_ENCRYPTION_KEY`, e.g. `User.mfa_secret`) — both **optional, off by default**, with a startup warning (not a hard failure) when unset.

None of MFA, account lockout, or ingest-token scoping have dedicated automated tests (confirmed by searching `backend/tests/unit/` for `lockout`/`totp`/`mfa`/`ingest_token` — zero matches). See [`04_TESTING_AND_VERIFICATION.md`](04_TESTING_AND_VERIFICATION.md).

## 8. AI/ML components — exactly where they are used

| Component | Where | In the live ingest path? |
|---|---|---|
| Drain3 (unknown-log clustering) | `app/ai/drain3_engine.py` | Yes — runs on every format-detection failure |
| `sentence-transformers` (semantic field-mapping similarity) | `app/ai/embeddings.py` | Only during parser onboarding/drafting, not per-event ingest |
| Ollama LLM (field-mapping fallback) | `app/ai/llm.py` | Only reached for a field name the deterministic alias table doesn't recognize, and only during onboarding — never in the per-event hot path. Disabled under `AIRGAPPED_MODE=true` (the default). |
| Sentinel (entity behavior) | `app/ai/sentinel.py` | Runs post-ingest, in the 30s background cycle, not inline |
| Event-risk classifier | `app/ai/event_classifier.py` | **No** — built, evaluated, deliberately not called anywhere (see doc 01 §9) |
| LinUCB triage bandit | `app/ai/triage_bandit.py` | **No** — offline-validated only, not wired to production case triage |

## 9. Deployment architecture

Three shapes exist in the repository; live-verification status for each is in [`05_INTEGRATION_AND_DEPLOYMENT_READINESS.md`](05_INTEGRATION_AND_DEPLOYMENT_READINESS.md):

1. **Local/dev, no Docker** (`backend/scripts/run_local_demo.py` + `npm run dev`) — what every number in this document set was measured against.
2. **Docker Compose** (`docker-compose.yml` dev-shaped; `docker-compose.prod.yml` overlay adds a TLS-terminating nginx front, drops host-published internal ports and bind mounts, sets `read_only: true` root filesystems on backend/worker/syslog-listener with a `tmpfs` `/tmp`).
3. **Kubernetes** (`deploy/k8s/`) — StatefulSets for Postgres/Redpanda, Deployments for backend/worker(x2)/syslog-listener, a namespace-wide default-deny NetworkPolicy plus explicit allows, kustomize-based image substitution for air-gapped registries.

## 10. Important integrations

- **Kafka/Redpanda**: `INGEST_BACKEND=kafka` publishes to a topic; `app/workers/main.py` consumes and calls the identical `process_raw_event()` the sync path uses.
- **MinIO**: object-store backend for the raw vault, wired but not the live-verified local path.
- **OpenSearch**: wired as the intended analyst-scale search target; PostgreSQL remains the system of record either way.
- **Ollama**: local LLM, field-mapping assist only, disabled under `AIRGAPPED_MODE`.
- **SoftHSM2 / any PKCS#11 module**: checkpoint signing (`KEY_BACKEND=pkcs11`).
- **A real external RFC 3161 TSA** (e.g. `freetsa.org`, `timestamp.digicert.com`): trusted timestamping, opt-in via `RFC3161_TSA_URL`.
- **A generic SMS HTTP gateway**: on-call notification, opt-in via `SMS_GATEWAY_URL`/`SMS_GATEWAY_API_KEY`.
