# 05 — Integration and Deployment Readiness

> Cross-references: [`01_PROJECT_OVERVIEW.md`](01_PROJECT_OVERVIEW.md), [`02_SYSTEM_ARCHITECTURE.md`](02_SYSTEM_ARCHITECTURE.md), [`03_FEATURES_TECH_STACK_AND_DATA.md`](03_FEATURES_TECH_STACK_AND_DATA.md), [`04_TESTING_AND_VERIFICATION.md`](04_TESTING_AND_VERIFICATION.md).

## Update — 2026-10-01 (live deployment session)

Everything below this point is the original audit, kept as-written for its historical findings. Since it was written, the project has actually been pushed to GitHub and deployed live (Render backend + Vercel frontend) — the §12 "NOT READY for a GitHub push" verdict below is **no longer current for those two specific reasons** (the push already happened; the deployment is live). The other original blockers (git hygiene at the time, the two failing tests, zero MFA/lockout/ingest-token test coverage) were **not** re-verified in this update and should still be treated as open unless re-checked.

Real, verified changes since this audit:
- **`AIRGAPPED_MODE` now actually enforces something.** The original audit (§3, §8) repeated the config default (`true`) and the project's own doc claim that it "blocks non-essential outbound calls" — that claim was false at the time; the flag was declared but never checked anywhere in the code. It now hard-blocks the Groq LLM fallback, webhook delivery, RFC3161 timestamping, and SMS when enabled.
- **A real air-gap blocker was found and fixed**: the sentence-transformers embedding model downloaded from HuggingFace Hub at runtime on first use if not cached — silently breaking a genuinely air-gapped install. It's now pre-downloaded at Docker build time and baked into the image.
- **OpenSearch / MinIO** (§1, listed as "not exercised"): OpenSearch indexing is now real, wired code (`app/services/event_delivery.py`), called on every real-time-ingested event. Still not demoable on the live Render deployment specifically (no OpenSearch instance hosted there), but functionally real — demoable via `docker compose up`.
- **Webhook export**, previously nonexistent, is now real and was verified live end-to-end: a real event was ingested, delivered to a real external endpoint, and the delivery was confirmed received within ~100ms.
- **A real, previously-undocumented security bug was found and fixed**: the Multi-CSE Supervisory rollup endpoint (`/supervisory/organizations`) had no authentication at all — confirmed via a direct unauthenticated call to the live production API returning real cross-org data. Now requires login, same as every other sensitive router.
- **`sbom/ulpf-dev-signing-key.asc`** (flagged in §7/§9 below as unconfirmed secret-exposure risk): verified in this update to be a PGP **public** key block (`-----BEGIN PGP PUBLIC KEY BLOCK-----`, no private-key marker) — public keys are meant to be distributed, so this specific file is not actually a leak. The other two paths named alongside it (`deploy/dev-ca/*.key`, `deploy/k8s/02-secret.yaml`) are correctly `.gitignore`d and were never tracked.
- **Real LLM field-mapping fallback added** (Groq, hosted API) — not present at all when this audit was written. See `03_FEATURES_TECH_STACK_AND_DATA.md`.

## 1. Integration matrix

| Integration point | Status | Evidence |
|---|---|---|
| Backend ↔ database | **Working** | Live SQLite queried directly throughout this audit (34,626 raw events, 34,608 normalized) |
| Backend ↔ frontend | **Working** | Frontend built clean against the live backend API shape this session; both processes confirmed running (`localhost:8000`, `localhost:5174`) |
| Ingestion ↔ parser | **Working** | 99.9% live parse success rate, 13 formats confirmed with real event counts |
| Parser ↔ normalization | **Working** | `unmapped`-preservation behavior confirmed by direct code read across every format branch |
| Normalization ↔ integrity | **Working** | Merkle leaf append is in the same transaction as the `NormalizedEvent` insert (direct code read); `test_integrity.py` passes |
| Integrity ↔ evidence verification | **Working** | Standalone verifier (`verifier/verify_bundle.py`) confirmed to import nothing from the app; prior project history documents a live byte-flip tamper-detection test passing |
| Analytics ↔ normalized events | **Working** | Correlation/Sentinel run post-ingest against real stored events (direct code read, `test_graph.py`/`test_sentinel.py` pass) |
| Correlation ↔ cases/alerts | **Working, but currently produces 0 live matches** | `live_detection.py` auto-opens a `Case` on a new `CorrelatedIncident`; the 3 starter rules match nothing against current real data — a real fact about data coverage, not a wiring failure (confirmed by `test_correlation.py`'s matching-logic tests passing while the rule-loading test itself fails — see §3 below) |
| AI parser workflow ↔ human approval | **Working** | Draft packs are created in `status="draft"` and gated behind the same publish endpoint as hand-authored parsers (direct code read, exercised live this session) |
| Kafka/Redpanda | **Live-verified in prior project history** against a real local Kafka broker (not re-verified in this specific audit pass) | `test_ingest_backend.py` passes (isolation-only tests, not a live broker test) |
| Redis | **Not connected in this audit's environment** | Live warning observed during this session's test run: "Rate limiting: Redis is unreachable — falling back to a per-process, non-shared in-memory limiter" |
| OpenSearch / MinIO | **Not exercised in this audit's environment** (local SQLite/filesystem path only) | Confirmed by `docker-compose.yml` not being the active runtime this session |
| Docker / Compose | **Not exercised in this audit** (backend/frontend run directly via `run_local_demo.py`/`npm run dev`, not via `docker compose up`) | Compose files read and structurally reviewed, not run, in this pass |
| Kubernetes | **Live-verified in prior project history** (real `kind` cluster, real smoke test) — **not re-verified in this audit pass** | See doc 01 §8 for the documented prior result |
| CI/CD | **Configured, not executed in this audit** (GitHub Actions requires a push/PR trigger) | `.github/workflows/ci.yml` read directly, 4 jobs confirmed present and structurally sound |
| Authentication/security integrations | **Working (core), untested (MFA/lockout/ingest-tokens)** | See doc 04 §7 |

## 2. Deployment prerequisites

- **Python 3.11** (Dockerfile/CI target; this audit's live environment actually runs Python 3.13.7 locally — confirmed via `pytest`'s own banner — which the project's own `requirements.txt` comments note was specifically accommodated for `psycopg2-binary`, but is **not** the pinned CI/Docker version; treat 3.11 as the verified target for anything shipped).
- **Node.js** current LTS (no explicit `engines` field in `package.json`).
- PostgreSQL 15 for the documented production path (SQLite is dev-only).
- Optional: Ollama (LLM field-mapping fallback — the pipeline works without it).

## 3. Required environment variables / secrets

Full list read directly from `backend/app/core/config.py` (~90 fields) and `.env.example`. Critical ones for any real deployment:

| Variable | Why it matters | Default if unset |
|---|---|---|
| `JWT_SECRET` | Session token signing | Auto-generated, process-lifetime-only, loud warning (not a hard failure unless `REQUIRE_JWT_SECRET=true`) |
| `POSTGRES_PASSWORD` / `POSTGRES_HOST` etc. | Database connection | Empty password by default — will fail to connect meaningfully |
| `VAULT_ENCRYPTION_KEY` | Raw-log-at-rest encryption | Unset = vault is compressed but **not encrypted**, warning only |
| `DB_ENCRYPTION_KEY` | Column-level encryption (e.g. MFA secret) | Unset = plaintext, warning only |
| `ADMIN_INITIAL_PASSWORD` | Bootstraps the first admin account | Empty = no admin auto-created |
| `CORS_ORIGINS` | Must match the actual frontend origin | Defaults include `:5173`/`:5174`/`:3000` only |
| `KEY_BACKEND` (+ `PKCS11_*`) | Checkpoint signing key location | `file` (demo-grade PEM on disk) |
| `SMS_GATEWAY_URL` / `_API_KEY` | Real on-call SMS delivery | Unset = `not_configured`, honest, never fabricated |
| `RFC3161_TSA_URL` | Real trusted timestamping | Unset = feature inactive (air-gapped default) |
| `AUTO_CHECKPOINT_EVERY_EVENT` | O(n) vs O(1)-ish checkpoint cost tradeoff | `true` — fine for a demo, a real high-volume deployment should set `false` + run `checkpoint_scheduler.py` |
| `ACCOUNT_LOCKOUT_THRESHOLD` / `_MINUTES` | Real brute-force protection | 5 attempts / 15 minutes |
| `AIRGAPPED_MODE` | Blocks non-essential outbound calls | `true` |

**Secrets currently present on disk in this repository** (real, found by direct listing — a genuine pre-push concern, not hypothetical): `deploy/dev-ca/ca.key`, `deploy/dev-ca/device-*.key`, `deploy/k8s/02-secret.yaml` (a real, filled-in Kubernetes Secret manifest, not just the `.example` template), `sbom/ulpf-dev-signing-key.asc`. These are documented as throwaway/dev-only in their respective contexts, but **must be confirmed excluded from any public GitHub push** — see §7.

## 4. Ports and services

| Service | Port | Source |
|---|---|---|
| Backend API | 8000 | confirmed live this session |
| Frontend dev server | 5173 (falls back to 5174) | confirmed live this session (5174) |
| PostgreSQL | 5432 | `docker-compose.yml` |
| MinIO | 9000 (API), 9001 (console) | `docker-compose.yml` |
| OpenSearch | 9200, 9600 | `docker-compose.yml` |
| OpenSearch Dashboards | 5601 | `docker-compose.yml` |
| Redis | 6379 | `docker-compose.yml` |
| Redpanda | 9092, 29092 | `docker-compose.yml` |
| Ollama | 11434 | `docker-compose.yml` |
| Syslog listener | 5514 (UDP+TCP, plaintext), 6514 (TCP, mTLS opt-in) | `docker-compose.yml`, `syslog_listener.py` |
| nginx (prod overlay) | 80, 443 | `docker-compose.prod.yml` |

## 5. Health checks

- Backend: `GET /api/v1/health` (confirmed live, responds `{"status":"healthy",...}`), plus Docker `HEALTHCHECK` directives in both Dockerfiles.
- Frontend Dockerfile healthcheck: a raw HTTP GET against the dev server root (note: the frontend Dockerfile runs `npm run dev`, not a production build served by a proper web server — see §8 warnings).
- Postgres: `pg_isready`, in compose.
- MinIO: `curl` against `/minio/health/live`, in compose.

## 6. Persistence requirements

- **Backend data directory** (`/app/data` in containers) must be a persistent named volume — holds the raw-log vault, the checkpoint signing key (file backend), and the SQLite fallback DB. `docker-compose.prod.yml` correctly wires this now (`backend_data` named volume); the base `docker-compose.yml` relies on a dev bind mount instead, which is fine for dev but would need the same named-volume treatment if run standalone in a non-dev context.
- Postgres/MinIO/OpenSearch/Redis/Redpanda each have their own named volumes in `docker-compose.yml`.

## 7. GitHub readiness checklist

| Item | Status |
|---|---|
| No secrets in tracked files | **NOT VERIFIED — real risk found.** `deploy/dev-ca/*.key`, `deploy/k8s/02-secret.yaml`, and `sbom/ulpf-dev-signing-key.asc` exist on disk. Whether they are already `.gitignore`d was not confirmed in this pass — **must be checked before any push**, since `.gitignore` itself shows as modified in the current working tree (`git status` — see below). |
| Working tree is clean / committed | **FAIL.** `git status --short` shows **210 changed paths** at the time of this audit — modified backend core/API/model files, modified frontend, modified `docker-compose*.yml`, a pending rename (`updated overviews.md` → `docs/PROJECT_OVERVIEW.md`), and more. This is a large amount of real, uncommitted work. |
| `.env` files excluded | **UNKNOWN** — not directly checked against `.gitignore` content in this pass. |
| Tests pass | **PARTIAL.** See doc 04 — 2 confirmed-real failures, reproduced in isolation (one correlation-rule-loading assertion, one rate-limiter that lets a 121st request through a 120-request budget), plus 3 more that failed only under this audit's own concurrent CPU load and were confirmed to pass cleanly in isolation (a real, documented characteristic of the sandbox test class under contention, not a code regression). |
| Frontend builds clean | **PASS**, confirmed this session. |
| CI config present and structurally sound | **PASS**, `.github/workflows/ci.yml` read directly. |

## 8. Deployment readiness checklist

| Item | Status |
|---|---|
| Local/dev path runs end-to-end | **PASS** — verified live this session (backend healthy, 99.9% parse success, frontend builds and serves) |
| Docker Compose path | **Structurally reviewed, not run in this audit pass** |
| Kubernetes path | **Live-verified in prior project history, not re-run in this audit pass** |
| Production frontend serving | **Real gap, confirmed by direct read**: `docker-compose.prod.yml`'s frontend service runs `npm run build && npm run preview` — Vite's own preview server, not a hardened production web server (e.g. nginx serving the static `dist/` output directly). Functional, but worth flagging as not the most robust production static-asset serving pattern. |
| Read-only root filesystem (Part D12) | **PASS, and more current than prior docs claimed** — `docker-compose.prod.yml` sets `read_only: true` + a `tmpfs` `/tmp` on backend/worker/syslog-listener. Prior documentation stated this was "not attempted"; the code has since moved past that claim (see doc 01 §9). |
| Secrets management | **Needs a real decision** — every signing/CA key in the repo today is a throwaway dev artifact, explicitly labeled as such in code comments. A real deployment needs its own CA, its own HSM/KMS-backed signing key, and secrets pulled from a real secrets manager, not `.env`. |
| Backup/recovery | **Not addressed anywhere in the codebase or docs found in this audit** — no backup script, no documented Postgres backup/restore procedure. **UNKNOWN / gap.** |
| Network/security requirements | CORS allowlist, CSP/security headers, rate limiting, and a default-deny Kubernetes NetworkPolicy are all real and confirmed present. mTLS exists for the syslog collector path only, by design (documented reasoning: the REST API/frontend boundary serves normal browser logins, where a client-cert requirement would break login rather than add protection against the actual threat model). |
| Offline / air-gapped operation | `AIRGAPPED_MODE=true` by default; the standalone verifier has no app dependency; a genuinely air-gapped install still needs base images pre-pulled and mirrored to an internal registry (`kustomize edit set image`) — documented, not automated. |

## 9. BLOCKERS — must be fixed before deployment / GitHub push

1. **210 uncommitted changes in the working tree**, including core backend logic, models, and both compose files. Pushing to GitHub in this state either loses this work (if `.gitignore`d/untracked and machine is lost) or pushes an uncontrolled, unreviewed diff. **Action**: review and commit deliberately, in reviewed chunks, before any push.
2. **Unconfirmed secret exposure**: real private key material (`deploy/dev-ca/*.key`, a filled `deploy/k8s/02-secret.yaml`, a signing key under `sbom/`) exists in the working tree and its `.gitignore` status was not confirmed in this audit. **Action**: explicitly verify every one of these paths is excluded before staging anything, and rotate any of them that may have already been committed to a prior git object even if since removed from the working tree (git history retains blobs).
3. **Two known-failing backend tests are not clean.** `test_starter_rules_load_and_are_well_formed` and the rate-limiter default-endpoint test fail consistently. A "GO" for deployment should not rest on an untriaged red test suite.
4. **Zero automated test coverage for MFA, account lockout, and ingest-scoped tokens** — real, live, security-relevant code paths with no verification they behave correctly under adversarial input.

## 10. WARNINGS — should be addressed, not necessarily blocking

1. Frontend bundle is a single 1.2 MB (341 KB gzip) JS chunk — Vite's own build flags this; code-splitting would improve load performance but does not affect correctness.
2. Production frontend serving uses Vite's `preview` mode rather than a dedicated static file server.
3. Dependency vulnerability scan (`pip-audit`/`npm audit`) was not re-run in this audit; prior findings (two known-CVE packages left pinned on purpose) should be re-checked against the current exact pin set.
4. No backup/recovery procedure exists for the primary database or the raw-log vault.
5. A full per-route audit of which "open" (no router-level auth) endpoints have real per-route auth versus none was not exhaustively completed in this pass (doc 02 §5).
6. Pipeline throughput benchmarks in prior project history were not re-measured in this audit — treat as indicative, not current, until re-run on an uncontended machine.

## 11. Claims in prior documentation that are no longer accurate (found this audit)

- **"Read-only root filesystem — not attempted."** (Prior `HARDENING.md`.) The current `docker-compose.prod.yml` sets `read_only: true` on three services. The code has moved past this claim.
- **"MFA: not started. Account lockout: not started. Separate ingest-vs-admin token identities: not built."** (Prior `GAP_REPORT_PHASE2.md`, Part D1.) All three are now real, implemented, and live in `app/api/v1/auth.py`, `app/core/security.py`, and `app/api/v1/admin.py` — though, per this audit's own finding, none have automated test coverage yet.
- **"Parse success rate ~99.9%."** Still independently confirmed accurate as of this audit (99.9% live), contrary to this task's own initial expectation of ~98% — reported as measured, per instruction, not adjusted to match either prior number.
- **Router/model/route counts in prior docs** (e.g. "21 routers," "~75-80 endpoints," "27-29 models") are all now undercounts — the live system has 30 routers, 153 total registered routes, and 34 models, directly counted in this audit.

## 12. Final assessment: GO / NOT READY

**NOT READY for a GitHub push or production deployment in its current state, based strictly on the evidence gathered in this audit.**

Reasons:
- A 210-path uncommitted working tree with unconfirmed secret-exclusion status is a hard blocker on its own — pushing now risks either losing real work or leaking real (if dev-grade) private key material.
- The backend test suite is not clean (2 consistently-failing tests, untriaged).
- Real, security-relevant code (MFA, lockout, ingest tokens) has zero automated verification.

What **is** genuinely ready: the core pipeline itself. 34,626 real events, 99.9% live parse success, a working Merkle-integrity chain, a clean frontend build, and CI configuration that structurally makes sense. The path to "GO" is short and mechanical, not a rewrite: resolve the git/secrets situation (§9.1-9.2), triage the two known test failures (§9.3), and add minimal coverage for the three untested security features (§9.4) — then this is a reasonable candidate for a controlled push and a documented-as-prototype deployment.
