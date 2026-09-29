# 01 — Project Overview

**Audit basis:** this document was produced by directly inspecting the running codebase at `C:\Users\Anshul\Desktop\PS156\PS156` on 2026-09-29 — source files read, live backend queried (`http://localhost:8000`), tests executed, builds run. It does not carry forward claims from prior documentation without re-verification. Where something could not be directly verified in this pass, it is marked **UNKNOWN**, not assumed true or false.

> **Cross-references:** architecture detail → [`02_SYSTEM_ARCHITECTURE.md`](02_SYSTEM_ARCHITECTURE.md). Full feature/tech-stack/data inventory → [`03_FEATURES_TECH_STACK_AND_DATA.md`](03_FEATURES_TECH_STACK_AND_DATA.md). Test results and matrix → [`04_TESTING_AND_VERIFICATION.md`](04_TESTING_AND_VERIFICATION.md). Deployment/integration readiness and GitHub-push blockers → [`05_INTEGRATION_AND_DEPLOYMENT_READINESS.md`](05_INTEGRATION_AND_DEPLOYMENT_READINESS.md).

---

## 1. Executive summary

ULPF (Universal Log Pre-processing Framework) is a log ingestion, normalization, and cryptographic-integrity platform built for **Smart India Hackathon Problem Statement 26156**. It takes heterogeneous security logs (firewalls, Windows Event Log, syslog appliances, cloud audit trails, application logs) arriving in different wire formats, detects the format, parses and normalizes each event into one canonical schema, redacts PII, scores risk, and appends every normalized event to an append-only, cryptographically signed Merkle tree so that tampering after the fact is independently detectable. On top of that pipeline sits a full analyst application: correlation, entity behavior profiling, incident case management, attack-path reconstruction, threat hunting, and parser authoring.

The backend is FastAPI + SQLAlchemy (153 registered routes across 30 routers, 34 ORM models, directly counted from the running app). The frontend is React 19 + TypeScript + Vite (29 page components, 26 routed paths). It is run and verified in this audit against a local SQLite database (`backend/data/local_demo.sqlite3`) containing **34,626 real ingested events** from independently-sourced public log corpora.

## 2. Problem being solved

Before any detection, search, or correlation logic can act on log data, that data has to be understood. A real deployment ingests logs from many vendors, each speaking a different format (CEF, LEEF, JSON, XML, key-value, CSV, freeform syslog text, and more), using different field names for the same concept. Two further requirements compound this: (1) a new, previously-unseen source should not require a developer to hand-write a bespoke parser, and (2) once a log is stored, it must be provable — to an auditor, an incident responder, or a court — that the stored copy is exactly what was originally received.

## 3. Exact solution

A synchronous processing pipeline (`backend/app/core/processing.py:process_raw_event`, verified by direct read) that, for every ingested log:

1. Hashes and vaults the raw bytes before anything else touches them.
2. Detects the format via a deterministic cascade (13 formats currently supported — full list in [`03_FEATURES_TECH_STACK_AND_DATA.md`](03_FEATURES_TECH_STACK_AND_DATA.md)).
3. Parses it, then normalizes it either via a human-approved "source pack" (YAML field-mapping config) or a hardcoded per-format mapper — either path preserves anything it couldn't map under an `unmapped` key rather than discarding it.
4. Redacts PII (email/Aadhaar/Indian mobile/PAN patterns) from the stored message.
5. Computes an explainable risk score (base + severity + action-keyword contributions, each listed).
6. Canonicalizes the event (RFC 8785 JSON Canonicalization Scheme) and appends its hash as a leaf to an RFC 6962-style Merkle tree, then (by default) issues a freshly signed checkpoint.
7. On failure, clusters the unparseable line (Drain3) and routes it to a dead-letter queue rather than dropping it.

Analyst-facing features (correlation, entity behavior, cases, graph, hunting, evidence export) are built on top of the resulting `NormalizedEvent` table — detailed in [`03_FEATURES_TECH_STACK_AND_DATA.md`](03_FEATURES_TECH_STACK_AND_DATA.md).

## 4. End-to-end user/system flow

```text
Log source (HTTP POST, syslog UDP/TCP/mTLS listener)
   -> raw bytes hashed (SHA-256), written to raw vault (append-only)
   -> format detected -> parsed -> normalized (source pack or deterministic)
   -> PII redacted -> risk scored -> canonicalized -> Merkle leaf appended
   -> signed checkpoint issued (default: after every event)
   -> NormalizedEvent row persisted (SQLite locally / PostgreSQL in the documented prod path)
   -> background 30s cycle: correlation rules + entity-behavior (Sentinel) re-evaluated,
      high/critical findings auto-open a Case with severity-tiered notification
   -> analyst (via ~26 frontend routes): searches events, inspects Merkle proofs,
      reviews/publishes parsers, works cases, runs hunts, exports evidence bundles
```

Full stage-by-stage detail with file/function citations: [`02_SYSTEM_ARCHITECTURE.md`](02_SYSTEM_ARCHITECTURE.md) §3.

## 5. Major features (summary — full inventory in doc 03)

- Multi-format ingestion and normalization (13 formats, real-data verified)
- Agentic unknown-format onboarding with a mandatory human-approval gate
- Signed, portable parser export/import/rollback
- Cryptographic integrity: Merkle tree, Ed25519/HSM-backed signed checkpoints, RFC 3161 trusted timestamps, multi-party witnessing, a standalone offline verifier
- Correlation engine (YAML-defined, cross-source-type rules)
- Entity behavior profiling ("Sentinel") — unsupervised, explainable
- Incident case management with severity-tiered on-call notification and escalation
- Entity graph, timeline, and attack-path reconstruction
- Threat hunting workspace (saved/audited queries)
- Evidence bundle export with a draft domestic (BSA §63) and international evidence-standards mapping
- MFA (TOTP) + account lockout + separate ingest-scoped tokens
- Retention policies and legal holds
- A real, offline-validated (against Microsoft's public GUIDE dataset) LinUCB alert-triage bandit — **not** wired into production triage

## 6. Current implementation status

Verified live against the running system on 2026-09-29:

| Metric | Value | How verified |
|---|---|---|
| Total raw ingested events | 34,626 | `GET /pipeline/health`, live query |
| Normalized events | 34,608 | same |
| **Parse success rate** | **99.9%** (34,608 / 34,627 — the health endpoint's own denominator) | same, live |
| Currently-failed (DLQ) events | 23 rows / **19 distinct events** (4 duplicate retry-artifact rows on already-failed test fixtures — a real, minor, known accounting quirk, not a new bug) | direct SQLite query against `dlq_events` |
| Backend routes registered | 153 (30 routers) | `import app.main; len(app.main.app.routes)`, run directly in this audit |
| ORM models | 34 | direct count of `class ` definitions in `app/models/all.py` |
| Frontend pages / routed paths | 29 / 26 | direct file/route count in `frontend/src/pages`, `frontend/src/main.tsx` |
| Backend test files / fuzz test file | 23 unit test files (~166 test functions) + 1 fuzz test file (15 property tests) | direct count |
| Frontend automated tests | **0** (no `.test.`/`.spec.` files found anywhere under `frontend/src`) | direct search |

**Important correction to a stated expectation:** this audit was asked to verify whether the current parse success rate is closer to 98% than a previously-claimed 99.9%. The live system, queried directly and independently in this pass, reports **99.9%**, not ~98%. The 19 real, distinct remaining failures are traced (§7 of [`03_FEATURES_TECH_STACK_AND_DATA.md`](03_FEATURES_TECH_STACK_AND_DATA.md)) to deliberately-malformed test/demo fixture sources (`NOVEL-FMT-TEST`, `WINEVT-ATTACK`, `REPARSE-TEST`, `PERSIST-TEST-*`, `FW-001`, `DEMO-FLOW-*`) — not real, previously-unparsed production data. This is reported as measured, not adjusted to match either number.

## 7. What makes the project novel

1. **Agentic unknown-format onboarding with a mandatory human gate.** An unparseable log is clustered (Drain3); an analyst can trigger a real LLM-assisted draft pack built from real clustered samples, which is created in `draft` status and must pass the same publish gate as a hand-authored parser — verified by reading `app/services/pack_drafting.py` and `app/api/v1/unknown_clusters.py`, and by exercising it live in this session (a genuinely undetectable sample now correctly returns a clean `undetectable_format` error rather than a silently-broken empty draft, after a real case-sensitivity bug was found and fixed).
2. **Continuous, real-time attack-propagation detection.** A 30-second background daemon thread (`app/services/live_detection.py`, started in `app/main.py`'s startup event) re-runs the same correlation + Sentinel logic the manual "evaluate" button calls, and auto-opens a `Case` with severity-tiered notification for new high/critical findings.
3. **Signed, portable parser sharing.** A published parser can be exported as a bundle signed with the same Ed25519/HSM key used for Merkle checkpoints (`app/api/v1/pack_sharing.py`), and re-imported elsewhere with signature verification before it is even saved as a draft.
4. **Cryptographic, independently-verifiable integrity.** An RFC 6962-style Merkle tree, Ed25519 (or PKCS#11/HSM-backed) signed checkpoints, optional RFC 3161 trusted timestamps against a real external TSA, optional multi-party witness cosignatures, and a completely standalone offline verifier (`verifier/verify_bundle.py`) whose only third-party dependency is the `cryptography` package — zero import from this application.

## 8. The most technically impressive / "crazy" aspects, explained factually

- **Live-tested Kubernetes deployment.** `deploy/k8s/` was not just schema-validated — a real `kind` cluster was stood up and the full stack deployed. Getting a clean run surfaced and fixed 6 real runtime bugs invisible to schema validation (a `runAsNonRoot`/`runAsUser` mismatch, an auto-injected `POSTGRES_PORT` collision, a renamed upstream Redpanda image, a dependency regression that only manifested in a genuinely fresh container build, a silently-swallowed Alembic migration failure masked by output buffering, and a duplicate-index migration bug that only surfaced the first time `alembic upgrade head` ever ran against real Postgres). The final state: a real event posted through the cluster, consumed by a real worker off a real Redpanda-compatible broker, normalized, and included in a real signed Merkle checkpoint with an independently verified signature.
- **Live-tested HSM-backed signing against a real PKCS#11 token** (SoftHSM2), including confirming the signer *refuses* rather than silently falls back to the weaker file-backed key on misconfiguration.
- **Live-tested mutual TLS** for the syslog collector path with real generated certificates: a connection with no client cert is rejected at the TLS handshake, before any log content is read; a connection with a valid cert succeeds and the device's real identity is captured in the event's provenance.
- **A real machine-learning result that was built, evaluated, and deliberately not shipped.** A TF-IDF + logistic-regression "malicious event" classifier scored 100% test accuracy; before trusting it, it was checked against a real, known-benign Windows Event Log record and confidently misclassified it 99.93% malicious — a log-format confound, not a working detector. The decision not to integrate it, with the full investigation, is documented and enforced by regression tests.
- **A real alert-triage bandit, offline-validated against a 9.5-million-row public SOC dataset** (Microsoft GUIDE, via Kaggle), reporting three different real experimental runs — including two weaker ones — rather than only the best-looking result, and correctly still refusing to go into production because it would need this system's own real analyst history, which doesn't exist yet.
- **A very large amount of self-correction visible in the code's own comments.** Repeatedly, a feature was built, then run against real data, and a real bug it exposed was found and fixed — documented inline at the fix site rather than only in a changelog (examples found directly in this audit: a Log4j/BGL-format detector case-sensitivity bug just fixed this cycle, a `POSTGRES_PORT` Kubernetes collision, an Ollama model that was never actually pulled on the demo machine, a Drain3 cluster-ID collision across restarts).

## 9. Key limitations and known gaps (honest, not hidden)

- **The default checkpoint-signing key is a file on disk** (`KEY_BACKEND=file`, the default). The HSM path exists and is live-verified, but is not the default.
- **No automated key rotation or CRL/OCSP-style revocation.**
- **SQLite is the actually-tested store for this audit's numbers.** PostgreSQL is the documented production default and is used by the live-tested Kubernetes/Kafka paths, but concurrent production-scale load has not been benchmarked in this pass — see [`04_TESTING_AND_VERIFICATION.md`](04_TESTING_AND_VERIFICATION.md).
- **The correlation engine's starter rules currently match 0 incidents** against the real seeded data — verified as an honest fact about current data coverage (checked per-rule in earlier project audits), not a bug.
- **SMS notification delivery has never sent a real SMS** — no gateway account exists in this environment; the code honestly reports `not_configured`.
- **MFA, account lockout, and ingest-scoped tokens are real, implemented, and currently have zero automated test coverage** — confirmed by direct search of `backend/tests/unit/` in this audit. This is a genuine gap this pass found that no prior documentation flagged.
- **The frontend has zero automated tests** (no `.test.`/`.spec.` files anywhere) — type-check, production build, and lint are the only frontend CI gates.
- **A very large amount of the working tree is currently uncommitted to git** (210 changed paths at time of audit, `git status --short`) — a direct blocker for a clean GitHub push; full detail in [`05_INTEGRATION_AND_DEPLOYMENT_READINESS.md`](05_INTEGRATION_AND_DEPLOYMENT_READINESS.md).
- **One vendor source pack (Palo Alto) is honestly-labeled synthetic** — no trustworthy real public sample could be found after checking multiple sources; a suspiciously "complete" candidate was rejected as likely AI-generated rather than passed off as real.
- **A real, previously-undocumented contradiction found in this audit**: `docs/HARDENING.md` (superseded by this document set) stated "read-only root filesystem — not attempted." The current `docker-compose.prod.yml`, read directly in this audit, sets `read_only: true` on the backend/worker/syslog-listener services with a `tmpfs` mount for `/tmp`. The code has moved past that documentation. This kind of drift is exactly why this audit re-verified against the code rather than trusting prior docs, per instruction.

## 10. Genuinely demonstrated versus planned

| Demonstrated (live-verified, this audit or a directly-cited prior one) | Planned / documented-only |
|---|---|
| Synchronous SQLite pipeline, 34,626 real events, 99.9% parse success | Production-scale concurrent load benchmarking |
| Kafka async ingestion path (real broker, real worker, real DLQ path) | — (already live-verified) |
| Kubernetes deployment (real `kind` cluster, real smoke test) | A CNI/NetworkPolicy enforcement audit beyond `kind`'s default |
| HSM-backed signing (real SoftHSM2 token) | A real production HSM/cloud KMS |
| Mutual TLS syslog collectors (real certs, real rejection test) | A real, non-throwaway production CA |
| RFC 3161 trusted timestamping (verified against two real public TSAs) | A qualified (eIDAS) timestamp from a Trust List QTSP |
| MFA + account lockout + ingest tokens (real code, confirmed present) | Automated test coverage for all three (currently none) |
| Correlation engine, Sentinel, entity graph, attack-path reconstruction | Correlation rules matching real current data (currently 0/3 rules match) |
| Alert-triage bandit, offline-validated against real public SOC data | Production use against this system's own analyst decisions |
| SBOM generation + signing, dependency audit | Automated CI enforcement of a zero-known-CVE gate |
