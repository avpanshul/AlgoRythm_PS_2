# 03 — Features, Tech Stack, and Data

> Cross-references: [`01_PROJECT_OVERVIEW.md`](01_PROJECT_OVERVIEW.md), [`02_SYSTEM_ARCHITECTURE.md`](02_SYSTEM_ARCHITECTURE.md).

## 1. Complete feature inventory (by frontend route)

Verified against `frontend/src/main.tsx`'s route table and each page's real backend calls (`frontend/src/api/client.ts`), cross-checked against the router list in doc 02 §5.

| Route | Page | What it does |
|---|---|---|
| `/dashboard` | `Dashboard.tsx` | Aggregate stats, pipeline health, sources, event-volume time series, recent cases |
| `/events`, `/events/:id` | `EventExplorer.tsx`, `EventDetail.tsx` | Search/filter normalized events; drill into canonical JSON, raw text, Merkle proof, version history; export (JSON/CSV/OCSF/CEF/syslog) |
| `/sources`, `/add-source` | `LogSources.tsx`, `AddLogSourceWizard.tsx` | Register a source; `analyze-sample` runs real format detection + LLM field classification against a pasted sample before committing |
| `/parsers` | `MappingRegistry.tsx` (Parser Lab) | Edit/test/publish source-pack YAML; the Unknown-format-clusters panel (draft-pack workflow) lives on the DLQ page, not here |
| `/replay` | `ReplayCenter.tsx` (Integrity & Replay) | Checkpoint inspection, replay jobs, a DLQ summary widget, audit log search |
| `/dlq` | `FailedEvents.tsx` (Failed Events / DLQ) | Full DLQ list (retry/resolve) + the Unknown-format-clusters / AI draft-pack panel |
| `/alerts` | `Alerts.tsx` (Analytics & Alerts) | Threshold rules CRUD + the correlation engine's manual-evaluate surface |
| `/graph` | `EntityGraph.tsx` (Entity Behavior & Graph) | Force-directed entity graph (react-force-graph-2d) + the full Sentinel risk-baseline table below it |
| `/attack-path` | `AttackPath.tsx` | Merged Attack Path + Timeline + Sparks: entity/incident search, path/timeline tabs, clickable re-pivoting |
| `/hunt` | `Hunt.tsx` (Threat Hunting) | Save/run/delete audited queries against normalized events |
| `/cases` | `Cases.tsx` (Incident Cases) | Manual + auto-opened cases, severity filter, notify/ack, on-call contacts |
| `/raw` | `RawVault.tsx` (Storage) | Inspect raw, pre-normalization vault entries |
| `/users` | `UserManagement.tsx` (Administration) | Users/roles/organizations CRUD |
| `/integrations` | `IntegrationsPage.tsx` (SIEM/Data Lake) | Outbound destination configs with a real connectivity test (real HTTP GET or real TCP connect, never a canned success) |
| `/evidence` | `Evidence.tsx` | Evidence bundle download, checkpoint list, coverage matrix |
| `/supervisory` | `Supervisory.tsx` | Aggregate-only multi-organization oversight view |

**Not reachable from the running app**: `ParserLab.tsx` exists in `frontend/src/pages/` but was found unwired in earlier project audits; not independently re-verified byte-for-byte in this pass — flagged as **UNKNOWN (needs re-check)** rather than restated as fact.

## 2. Technology stack

### Backend

| Layer | Technology | Verified via |
|---|---|---|
| Web framework | FastAPI 0.104, Uvicorn | `requirements.txt` |
| ORM / migrations | SQLAlchemy 2.0.23, Alembic 1.12.1 | `requirements.txt` |
| Validation | Pydantic v2.5.2 / pydantic-settings 2.1.0 | `requirements.txt` |
| Database driver | psycopg2-binary 2.9.13, asyncpg 0.29.0 | `requirements.txt` |
| Object storage / search / cache | minio 7.2.0, opensearch-py 2.4.2, redis 5.0.1 | `requirements.txt` |
| Streaming | confluent-kafka 2.3.0 | `requirements.txt` |
| Log clustering | drain3 0.9.11 | `requirements.txt` |
| Embeddings | sentence-transformers 2.2.2, numpy 2.2.6, pandas 2.3.3 | `requirements.txt` |
| Local LLM client | ollama 0.1.3 | `requirements.txt` |
| Auth | PyJWT 2.10.1, passlib[bcrypt] 1.7.4, bcrypt 4.0.1, pyotp 2.9.0 | `requirements.txt` |
| Crypto | cryptography 50.0.1, python-pkcs11 0.10.0, rfc3161ng 2.1.3 | `requirements.txt` |
| Testing | pytest 7.4.3, hypothesis 6.168.1, httpx 0.25.2 | `requirements.txt` |

### Frontend

| Layer | Technology | Verified via |
|---|---|---|
| Framework | React 19.2.8, TypeScript, Vite 8.3.0 | `package.json` |
| Routing | react-router-dom 7.18.4 | `package.json` |
| Data fetching | @tanstack/react-query 5.103.2 | `package.json` |
| HTTP client | axios 1.20.0 | `package.json` |
| Charts | recharts 3.10.1 | `package.json` |
| Graph visualization | react-force-graph-2d 1.29.1 | `package.json` |
| Styling | tailwindcss 4.3.3 | `package.json` |
| Linting | oxlint 1.81.0 | `package.json` |

### Database / AI / Security / Infrastructure / Testing (grouped, cross-referencing above)

- **Database**: PostgreSQL 15 (prod default) / SQLite (local dev, this audit's basis).
- **AI/ML**: Drain3, sentence-transformers, Ollama (LLM), a real hand-built LinUCB bandit (`triage_bandit.py`, no ML framework dependency), TF-IDF+logistic-regression classifier (`scikit-learn`-based, per `train_event_classifier.py` — not in `requirements.txt`'s runtime deps, confirms it's an offline training-only script, not a production dependency; **UNKNOWN** exactly which package provides it without re-reading that script's own imports, not done in this pass).
- **Security**: JWT, bcrypt, TOTP MFA, Fernet encryption, Ed25519/HSM signing, RFC 3161, mTLS.
- **Infrastructure**: Docker, docker-compose, Kubernetes (`kustomize`), GitHub Actions CI, Redpanda/Kafka, MinIO, OpenSearch, Redis.
- **Testing**: pytest, Hypothesis (property-based fuzzing), `tsc`/`vite build`/`oxlint` (frontend has no runtime test framework installed — see doc 04).

## 3. Supported log formats (13, live-verified)

| Format | Live event count (this audit) | Real source |
|---|---|---|
| JSON | 11,115 | Structured app/API logs, AWS CloudTrail |
| XML | 6,067 | Windows Event Log (incl. MITRE ATT&CK-tagged captures) |
| Syslog (RFC 3164/5424) | 5,852 | OpenSSH via the system syslog daemon |
| Log4j-pattern | 2,550 | Hadoop YARN, Apache Zookeeper |
| HDFS/Hadoop daemon log | 1,900 | HDFS DataNode/NameSystem logs |
| HPC node-event log | 1,899 | HPC cluster events |
| BlueGene/L (BGL) RAS log | 1,881 | The canonical public BGL supercomputer event format |
| Apache httpd error log | 1,478 | Web server error logs |
| Windows CBS/trace log | 977 | Windows servicing traces |
| CSV | 832 | Tabular/exported log data |
| KeyValue | 57 | Firewall/appliance free-text `key=value` logs |
| CEF | supported, 0 in current live dataset | — |
| LEEF | supported, 0 in current live dataset | — |

(Numbers re-queried live against `GET /pipeline/health` / `GET /stats` at the time of this audit; may drift slightly session-to-session as demo/test scripts run.)

## 4. Parser / source-pack architecture

- **Deterministic parsers** (`app/parsers/deterministic.py`) — one function per format, no LLM.
- **Source packs** (`Parser.config_json`, executed by `app/parsers/mapping_engine.py:apply_source_pack`) — YAML-shaped field mappings: `field_mappings` (dotted-path or literal-dotted-key, `list_mode: coalesce|join`), `regex`/`regex_group` extraction from free text, `static` values. Only takes effect once `status == "published"`, gated by a real fixture test (`app/parsers/sandbox.py`, isolated OS process + wall-clock timeout).
- **9 baseline vendor packs** (`backend/scripts/seed_vendor_packs.py`): Cisco ASA, Squid, pfSense, Suricata EVE, FortiGate, Windows Firewall, Zeek, AWS CloudTrail — all backed by real, independently-sourced samples (vendor docs or real test fixtures from projects like Elastic Beats). **Palo Alto is explicitly synthetic** — the script's own docstring records that no trustworthy real sample could be found.
- **Agentic drafting** (`app/services/pack_drafting.py`) — draws real samples from a Drain3 cluster, classifies fields via the deterministic alias table or the LLM fallback, assembles a draft pack (`status="draft"`), never auto-publishes.
- **Signed export/import/rollback** (`app/api/v1/pack_sharing.py`) — reuses the checkpoint-signing key.

## 5. Normalization schema

Canonical event JSON (built in `process_raw_event`, documented field-by-field):

| Key | Contents |
|---|---|
| `event_id` | Assigned at ingestion |
| `timestamp` / `ingested_at` | Event's own time if recognized, else ingestion time (`normalization.timestamp_source` records which) / always-ingestion time |
| `event` | ECS-like `{category, type, action, severity, outcome}` |
| `source` / `destination` | `{ip, port}` |
| `network` | `{protocol}`, IANA-normalized when a bare protocol number was given |
| `device` | `{vendor, product}` |
| `user` | `{name}` or `null` |
| `parser` | `{format, parser_version, parser_id}` |
| `normalization` | `{mapping_method, confidence, timestamp_source}` |
| `provenance` | `{raw_event_id, raw_sha256}` |
| `risk` | `{score, level, reasons[], thresholds, baseline}` |
| `quality` | `{score, epistemic}` |
| `message` | PII-redacted |
| `ocsf` | Best-effort OCSF 1.x mapping (not a compliance claim) |
| `unmapped` | Everything extracted but not mapped to a named field |

## 6. AI / LLM / ML usage

See doc 02 §8 for exactly which pipeline stage each touches. Summary of maturity:

| Component | Status |
|---|---|
| Drain3 clustering | In production path |
| Embedding similarity (field mapping) | In production path (onboarding only) |
| Ollama LLM (field mapping) | In production path (onboarding only, fallback of a fallback) |
| Groq hosted LLM (field mapping) | **Added 2026-10-01.** Real gap found live: this deployment has no reachable Ollama server (no process actually running at `OLLAMA_URL`), so the LLM fallback above silently produced `UNKNOWN`/0% confidence in production. `app/ai/llm.py` now tries a real hosted API (Groq, OpenAI-compatible) first when `GROQ_API_KEY` is set, falling back to the original Ollama behavior otherwise — purely additive, no regression for a real local Ollama install. Blocked under `AIRGAPPED_MODE` (a real external cloud API, unlike `OLLAMA_URL`, which in a real docker-compose deployment points at a container on the same internal network). Verified live against real unrecognized Zeek field names (`id.orig_h` → `source.ip`, 0.99 confidence, correct reasoning). |
| Sentinel behavioral profiling | In production path (background cycle) |
| Event-risk classifier | Built, evaluated, **not integrated** — a real 100% test-accuracy result was traced to a format confound (a real benign Windows Event Log record scored 99.93% "malicious") and deliberately not shipped |
| LinUCB triage bandit | Built, offline-validated against real public data, **not in production** — correctly blocked on needing this system's own real case-triage history |

## 7. Cryptography / integrity technologies

- RFC 6962-style Merkle tree (custom implementation, `app/integrity/merkle.py`)
- RFC 8785 JSON Canonicalization Scheme (custom implementation, `app/integrity/canonical_json.py`)
- Ed25519 signing (file-backed, default) or ECDSA P-256 via PKCS#11/HSM (`app/integrity/signing.py`)
- RFC 3161 trusted timestamping (`app/integrity/rfc3161.py`, `rfc3161ng`)
- Multi-party witness cosigning (`app/integrity/witness.py`)
- A standalone offline verifier (`verifier/verify_bundle.py`) — zero import from this application; its only third-party dependency is the `cryptography` package (used for Ed25519/ECDSA signature verification), confirmed by direct read of its imports.

## 8. Real datasets and data sources — exact repository paths

| Corpus | Path | Real lines | Real source |
|---|---|---|---|
| loghub-derived (OpenSSH, HDFS/Hadoop/Zookeeper, HPC/BGL, Apache, Windows) | `backend/datasets/real/corpus.jsonl` | 19,000 | logpai/loghub public corpora |
| Windows Event Log, attack-technique captures | `backend/datasets/real/evtx_corpus.jsonl` | 4,633 | sbousseaden/EVTX-ATTACK-SAMPLES (MIT), MITRE ATT&CK-tagged |
| Zeek/Bro IDS engine output | `backend/datasets/real/zeek_corpus.jsonl` | 8,159 | Real Zeek/Bro output incl. a genuine Team Cymru Malware Hash Registry match with a corroborating VirusTotal link |
| AWS CloudTrail | `backend/datasets/real/cloudtrail_corpus.jsonl` | 2,900 | invictus-ir/aws_dataset (MIT), a real Stratus Red Team attack simulation |

Build scripts (also under `backend/datasets/real/`): `build_corpus.py`, `build_evtx_corpus.py`, `build_zeek_corpus.py`, `build_cloudtrail_corpus.py`. Total across the 4 files: **34,692 real lines** (directly counted, `wc -l`), closely matching the live `total_raw_events` figure of 34,626 (small delta from a handful of test/demo-injected events and header/formatting rows, not investigated further in this pass).

**Real vs. synthetic, stated plainly**: all four corpora above are genuine third-party data with checkable provenance. The one deliberately synthetic component in the whole dataset picture is the Palo Alto vendor pack sample (§4). Everything else — including the 9 vendor-pack samples besides Palo Alto — is sourced from a real, independently checkable capture or a vendor's own published documentation example, per `seed_vendor_packs.py`'s own provenance docstring (read directly in this audit).

## 9. External services / integrations

| Service | Real, live-tested in this project's history? |
|---|---|
| Apache Kafka (as a Redpanda substitute) | Yes — a real local broker, real worker consumption, real DLQ path |
| SoftHSM2 (PKCS#11) | Yes — real token, real keygen, real signature, real rejection tests |
| `openssl s_client` mutual TLS | Yes — real generated certs, real handshake rejection/acceptance |
| Real public RFC 3161 TSAs (`freetsa.org`, `timestamp.digicert.com`) | Yes — real tokens obtained and verified |
| Real `kind` Kubernetes cluster | Yes — full stack deployed, real smoke test passing |
| Datadog Logs intake API (`http-intake.logs.datadoghq.com`) | Real, public, documented endpoint — connectivity-tested live in this session (real HTTP 403, no API key configured) |
| Google Chronicle/SecOps ingestion (`malachiteingestion-pa.googleapis.com`) | Real, public, documented endpoint — connectivity-tested live in this session (real HTTP 404) |
| AWS S3 / Google Cloud Storage | Real global endpoints — connectivity-tested live in this session (real TCP connect succeeded) |
| A real SMS gateway account | **No** — none exists in this environment; the code path is real but reports `not_configured` |
| A real production HSM/KMS | **No** — SoftHSM2 is a software stand-in |

## 10. Most important technical design decisions

- **Append-only, hash-based integrity rather than access-control-only.** A leaf's hash is never modified after being recorded — even a legitimate later re-processing (Replay) upserts the `NormalizedEvent` row but never mutates the existing Merkle leaf, preserving the append-only property the whole tamper-evidence design depends on (this exact invariant was the subject of a real bug fix earlier in this project's history, now covered by regression tests).
- **Preserve, never discard, unmapped fields.** Every normalization path keeps a parser's leftover fields under `unmapped` rather than silently dropping data the pipeline doesn't yet have a named slot for.
- **Fail visibly, not silently.** A misconfigured HSM refuses to sign rather than falling back to the weaker file key; an unconfigured SMS gateway reports `not_configured` rather than claiming delivery; optional infra (MinIO/OpenSearch/Kafka) failing at startup is caught and logged, not allowed to crash the app or silently pretend to work.
- **Agentic, never autonomous, onboarding.** Every AI-assisted output (a drafted parser, an LLM field-mapping suggestion) requires a real human approval step before it can affect live traffic.
- **Honest empty states over fabricated ones.** Confirmed throughout the UI and this document set's own data: zero real events for a format/source shows as zero, not a synthetic-looking placeholder.
