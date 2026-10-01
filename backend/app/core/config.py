import os
import json
import secrets
import warnings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Universal Log Pre-processing Framework"
    API_V1_STR: str = "/api/v1"

    # Postgres
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "ulp")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "ulp_db")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")

    # Managed-Postgres hosts (Render, Heroku, Railway, ...) hand you one
    # connection string, not five separate POSTGRES_* values -- if DATABASE_URL
    # is set, it wins outright rather than requiring it to be manually split
    # apart into POSTGRES_HOST/PORT/USER/PASSWORD/DB by hand (a real, easy
    # deployment mistake otherwise). Some providers (Render included) still
    # hand out the legacy "postgres://" scheme; SQLAlchemy's psycopg2 dialect
    # only accepts "postgresql://", so that's normalized here too.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://"):]
            return url
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Kafka / Redpanda
    KAFKA_BROKERS: str = os.getenv("KAFKA_BROKERS", "localhost:9092")
    # Pluggable ingestion backend (ULPF-phase2-prompt.md E5): "sync" (default)
    # processes each event immediately in the request handler -- what every
    # test, the local demo, and every seeded dataset in this project uses.
    # "kafka" instead publishes to Redpanda (already in docker-compose.yml,
    # Kafka-API-compatible) and lets app/workers/main.py consume + process
    # asynchronously, for sites that need ingestion to outpace synchronous
    # processing. Raw-log capture + hashing always happens synchronously in
    # both modes (see api/v1/ingestion.py:process_single_log) -- only
    # normalization/scoring/Merkle-append is deferred under "kafka".
    INGEST_BACKEND: str = os.getenv("INGEST_BACKEND", "sync")

    # MinIO
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "admin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    MINIO_RAW_BUCKET: str = "raw-events"

    # OpenSearch
    OPENSEARCH_URL: str = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
    OPENSEARCH_INDEX: str = "normalized-events"

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # AI Models
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    # Real bug found live (2026-09-28 audit): "phi3:mini" was never actually
    # pulled on the dev/demo machine -- every real LLM call failed with a
    # 404 "model not found", meaning pack drafting classified 0% of fields
    # in the exact environment this project runs its own demo in. Defaulted
    # to the model that's actually installed here (`ollama list` confirmed
    # only llama3.2:latest is present). Override with your own pulled model
    # via this env var; there is no code-level dependency on which one.
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
    # Also found live: the hardcoded 60s request timeout in app/ai/llm.py
    # was too tight for this model's real CPU-only inference time with the
    # actual production prompt (a short test prompt alone took ~30s here) --
    # every field classification timed out. Now configurable per-deployment
    # (faster/GPU hardware can lower it; slower CPU-only boxes can raise it)
    # instead of a silent hardcoded constant.
    OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # Hosted LLM fallback for field-mapping classification (app/ai/llm.py).
    # Real gap found live: this deployment has no reachable Ollama server
    # (only localhost:11434 is ever configured, which doesn't exist on a
    # single-container host like Render), so every LLM-assisted field
    # classification silently fell back to UNKNOWN. Self-hosting a real
    # Ollama model isn't realistic on a memory-constrained free instance
    # (even a small model needs several GB of RAM). A hosted API call is the
    # same shape of request this code already makes (one HTTP POST, no local
    # model, no extra memory) -- just pointed at a real endpoint instead of
    # an empty one. GROQ_API_KEY unset = this stays fully inert and the code
    # falls back to the existing OLLAMA_URL behavior, so local dev with a
    # real Ollama install is unaffected.
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    # Real bug found live: "llama-3.1-8b-instant" (a common Groq example
    # model name) returned a real 404 model_not_found from Groq's own API --
    # confirmed via a direct call to GET /openai/v1/models with the real
    # deployed key that it's no longer in Groq's served model list.
    # openai/gpt-oss-20b confirmed actually available and working (real
    # test call, correctly reasoned a sample field mapping with 0.95
    # confidence and a real explanation).
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    GROQ_TIMEOUT_SECONDS: int = int(os.getenv("GROQ_TIMEOUT_SECONDS", "20"))
    
    # Security
    #
    # JWT_SECRET MUST be set via env in any real deployment. We deliberately do NOT
    # ship a hardcoded fallback (the old default "super-secret-key-change-in-production"
    # was committed to source and .env, so anyone with repo access could forge tokens).
    #
    # Choice made here: fail loud in production-shaped configs, but degrade gracefully
    # for local/demo use by auto-generating a random secret and printing a loud warning.
    # A generated secret is process-lifetime only -- restarting the API invalidates all
    # previously issued tokens (everyone has to log in again). Set JWT_SECRET explicitly
    # (e.g. `openssl rand -hex 32`) to avoid that and to run more than one API instance.
    _jwt_secret_env = os.getenv("JWT_SECRET", "").strip()
    if _jwt_secret_env:
        JWT_SECRET: str = _jwt_secret_env
    elif os.getenv("REQUIRE_JWT_SECRET", "false").lower() == "true":
        raise RuntimeError(
            "JWT_SECRET is not set and REQUIRE_JWT_SECRET=true. Refusing to start. "
            "Set JWT_SECRET in the environment/.env (e.g. `openssl rand -hex 32`)."
        )
    else:
        JWT_SECRET: str = secrets.token_hex(32)
        warnings.warn(
            "JWT_SECRET is not set. Generated a random, process-lifetime-only secret. "
            "All issued tokens will be invalidated on restart and tokens will not be "
            "valid across multiple API instances. Set JWT_SECRET in .env for real use "
            "(and set REQUIRE_JWT_SECRET=true to make a missing secret a hard startup error).",
            stacklevel=2,
        )

    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

    # Initial admin bootstrap. If set, an "admin" user/role is created on first startup
    # (only if no users exist yet) with this password (bcrypt-hashed, never stored raw).
    # No default is provided on purpose -- if unset, no admin account is auto-created and
    # an operator must create one out-of-band.
    ADMIN_INITIAL_EMAIL: str = os.getenv("ADMIN_INITIAL_EMAIL", "admin@ulpf.local")
    ADMIN_INITIAL_PASSWORD: str = os.getenv("ADMIN_INITIAL_PASSWORD", "")

    # CORS - explicit origin allowlist (required when allow_credentials=True; browsers
    # reject a wildcard "*" origin combined with credentials anyway).
    # Real bug found live: the merged frontend-handoff dev server landed on
    # :5174 (port 5173 was already taken by the old frontend at the time),
    # and this list didn't include it -- every browser request was silently
    # blocked by CORS before it ever reached this backend, which is exactly
    # what "no data on the frontend" looks like (network tab shows CORS
    # errors, not 401s/500s). Both dev ports are listed now.
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:3000")

    # Logic Configuration
    RISK_WEIGHTS: dict = json.loads(os.getenv("RISK_WEIGHTS", '{"severity": 0.3, "action": 0.2, "frequency": 0.2, "asset": 0.15, "correlation": 0.15}'))
    CONFIDENCE_THRESHOLDS: dict = json.loads(os.getenv("CONFIDENCE_THRESHOLDS", '{"auto_approve": 0.90, "review": 0.70}'))

    AIRGAPPED_MODE: bool = os.getenv("AIRGAPPED_MODE", "true").lower() == "true"

    # MFA + account lockout (Part D1).
    MFA_ISSUER_NAME: str = os.getenv("MFA_ISSUER_NAME", "ULPF")
    ACCOUNT_LOCKOUT_THRESHOLD: int = int(os.getenv("ACCOUNT_LOCKOUT_THRESHOLD", "5"))
    ACCOUNT_LOCKOUT_MINUTES: int = int(os.getenv("ACCOUNT_LOCKOUT_MINUTES", "15"))
    # How long a pre-auth token (issued after password is correct but before
    # the TOTP code is checked) is valid for -- short, since it's a partial
    # login, not a real session.
    MFA_PREAUTH_EXPIRE_MINUTES: int = int(os.getenv("MFA_PREAUTH_EXPIRE_MINUTES", "5"))

    # Automatic re-ingestion scheduler (app/services/auto_ingest.py): feeds
    # the real, already-licensed AWS CloudTrail corpus (datasets/real/cloudtrail_corpus.jsonl)
    # through the real pipeline twice a day, deduped against what's already
    # ingested. AUTO_INGEST_TIMES is a comma-separated list of "HH:MM" (server
    # local time, 24h) slots; AUTO_INGEST_BATCH_SIZE caps how many new rows a
    # single run processes synchronously, so one run of the background thread
    # doesn't block everything else for the time it takes to walk the whole
    # remaining corpus.
    AUTO_INGEST_ENABLED: bool = os.getenv("AUTO_INGEST_ENABLED", "true").lower() == "true"
    AUTO_INGEST_TIMES: str = os.getenv("AUTO_INGEST_TIMES", "08:00,20:00")
    AUTO_INGEST_BATCH_SIZE: int = int(os.getenv("AUTO_INGEST_BATCH_SIZE", "300"))
    # How often the scheduler thread wakes up to check whether a configured
    # slot has arrived -- polling, not wall-clock-exact, same tradeoff
    # live_detection.py's 30s cycle already makes elsewhere in this codebase.
    AUTO_INGEST_POLL_SECONDS: int = int(os.getenv("AUTO_INGEST_POLL_SECONDS", "30"))

    # Ingest-scoped tokens (Part D1: separate ingest-vs-admin token identities).
    # Long-lived by default -- these back unattended forwarders/collectors
    # that can't interactively re-login every few hours the way a human user
    # can; they're still individually revocable via app/models/all.py's
    # IngestToken table (see app/api/v1/admin.py's /admin/ingest-tokens routes).
    INGEST_TOKEN_EXPIRE_DAYS: int = int(os.getenv("INGEST_TOKEN_EXPIRE_DAYS", "365"))

    # Checkpoint-signing key backend (ULPF-master-prompt.md Part D3). "file"
    # (default) is the demo-grade Ed25519 PEM-on-disk store this project has
    # always used -- fine for a demo, not for "the signing key never touches
    # app disk." "pkcs11" moves signing into a real or software HSM (tested
    # against SoftHSM2) via python-pkcs11: the private key is generated
    # inside the token and never leaves it. See app/integrity/signing.py and
    # docs/KEY_CEREMONY.md.
    KEY_BACKEND: str = os.getenv("KEY_BACKEND", "file")
    PKCS11_MODULE_PATH: str = os.getenv("PKCS11_MODULE_PATH", "")
    PKCS11_TOKEN_LABEL: str = os.getenv("PKCS11_TOKEN_LABEL", "ulpf-checkpoint-hsm")
    PKCS11_PIN: str = os.getenv("PKCS11_PIN", "")
    PKCS11_KEY_LABEL: str = os.getenv("PKCS11_KEY_LABEL", "ulpf-checkpoint-signing-key")

    # Incident notification channel (ULPF-phase2-prompt.md E6). User's
    # choice: SMS, via a generic HTTP gateway (the pattern most SMS
    # providers -- Twilio, MSG91, Fast2SMS, etc. -- actually use). Unset by
    # default: with no gateway configured, notifications are recorded as
    # "not_configured" rather than pretending to have been sent -- this
    # project has no real SMS gateway account to send through, and building
    # against a fake one would be fabrication, not a feature. See
    # app/notifications/channels.py and docs/GAP_REPORT_PHASE2.md's E6 row.
    SMS_GATEWAY_URL: str = os.getenv("SMS_GATEWAY_URL", "")
    SMS_GATEWAY_API_KEY: str = os.getenv("SMS_GATEWAY_API_KEY", "")
    SMS_GATEWAY_SENDER_ID: str = os.getenv("SMS_GATEWAY_SENDER_ID", "ULPF")
    # Escalation timeout for an unacknowledged critical-severity notification
    # before it escalates to the next on-call contact.
    ESCALATION_TIMEOUT_MINUTES: int = int(os.getenv("ESCALATION_TIMEOUT_MINUTES", "15"))
    NOTIFICATION_DEDUP_MINUTES: int = int(os.getenv("NOTIFICATION_DEDUP_MINUTES", "30"))
    NOTIFICATION_RATE_LIMIT_PER_HOUR: int = int(os.getenv("NOTIFICATION_RATE_LIMIT_PER_HOUR", "10"))

    # Merkle checkpoints: create_checkpoint() recomputes the tree root over
    # every leaf in the log (see app/integrity/service.py), so it's O(n) per
    # call. Checkpointing after every single ingested event -- the default,
    # so "prove this event" always works immediately after ingest -- makes
    # total ingestion cost O(n^2) (measured: ~290 events/s at n=300 dropping to
    # ~110 events/s at n=1500; see docs/benchmarks.md). Set this false and run
    # app/workers/checkpoint_scheduler.py instead once ingestion volume outgrows
    # what per-event checkpointing can keep up with.
    AUTO_CHECKPOINT_EVERY_EVENT: bool = os.getenv("AUTO_CHECKPOINT_EVERY_EVENT", "true").lower() == "true"

    # Item 2: spark detection (app/services/spark_detection.py). Off by
    # default -- additive, new behavior gated behind its own flag per this
    # task's rule. SPARK_RISK_THRESHOLD is the second explicit trigger rule
    # (an EntityProfile.risk_score crossing this value), alongside "first
    # event of a newly-opened CorrelatedIncident" (always on when the flag
    # is on, no threshold to configure for that half).
    ENABLE_SPARK_DETECTION: bool = os.getenv("ENABLE_SPARK_DETECTION", "false").lower() == "true"
    SPARK_RISK_THRESHOLD: float = float(os.getenv("SPARK_RISK_THRESHOLD", "80"))
    # Real scale problem found live (2026-09-29): this project's own demo DB
    # already has 132 entities at/above the default threshold, and each
    # spark does a real O(n) forward-time scan (reconstruct_attack_path) --
    # uncapped, one 30s cycle could trigger 132 full table scans. Capped per
    # cycle, highest-risk-first, same "bounded, capped per run" pattern
    # already used elsewhere in this codebase (AUTO_INGEST_BATCH_SIZE,
    # CHECKPOINT_REVERIFY_BATCH_SIZE) -- entities not reached this cycle are
    # picked up on a later one, never silently dropped forever.
    SPARK_MAX_NEW_PER_CYCLE: int = int(os.getenv("SPARK_MAX_NEW_PER_CYCLE", "5"))

    # Item 3: backlog re-parse (app/services/auto_reparse.py). Off by default.
    ENABLE_AUTO_REPARSE: bool = os.getenv("ENABLE_AUTO_REPARSE", "false").lower() == "true"
    AUTO_REPARSE_BATCH_SIZE: int = int(os.getenv("AUTO_REPARSE_BATCH_SIZE", "100"))

    # Item 4: Drain3 template-store persistence (app/ai/drain3_engine.py).
    # Real bug found live (2026-09-28 audit): the TemplateMiner was an
    # in-memory-only singleton -- every backend restart reset its cluster-ID
    # counter to 1, colliding with old UnknownTemplate DB rows from a
    # previous process lifetime (reproduced: 5 brand-new, unrelated log
    # lines got assigned cluster IDs 1-5, silently merging their samples
    # into 9-month-old unrelated SSH clusters). Off by default per this
    # task's flag rule; the counter-reseed safety net below (always on,
    # zero behavior change otherwise) still helps even with this off.
    ENABLE_DRAIN_PERSIST: bool = os.getenv("ENABLE_DRAIN_PERSIST", "false").lower() == "true"

    # Item 5: agent refine loop (app/services/pack_drafting.py). Off by
    # default; single-pass classification (Item 1's behavior) remains the
    # fallback when this is off or an attempt makes no further progress.
    ENABLE_AGENT_REFINE: bool = os.getenv("ENABLE_AGENT_REFINE", "false").lower() == "true"
    AGENT_REFINE_MAX_ATTEMPTS: int = int(os.getenv("AGENT_REFINE_MAX_ATTEMPTS", "3"))

    # Scheduled checkpoint self-verification (app/workers/checkpoint_scheduler.py):
    # re-walks previously-issued checkpoints (recompute their root from the
    # current leaf table + re-check their signature) rather than only ever
    # issuing new ones -- catches a leaf row altered/deleted after the fact,
    # which issuing new checkpoints alone would never notice. Capped per
    # cycle so re-verifying a large checkpoint history doesn't dominate.
    CHECKPOINT_REVERIFY_INTERVAL_HOURS: int = int(os.getenv("CHECKPOINT_REVERIFY_INTERVAL_HOURS", "24"))
    CHECKPOINT_REVERIFY_BATCH_SIZE: int = int(os.getenv("CHECKPOINT_REVERIFY_BATCH_SIZE", "5"))

    # RFC 3161 trusted timestamping (app/integrity/rfc3161.py). Unset by
    # default: no real TSA is configured out of the box (air-gapped-by-default
    # -- this would be an outbound network call to a third party on every
    # checkpoint), same pattern as SMS_GATEWAY_URL. A real free public TSA
    # for testing: http://freetsa.org/tsr (also http://timestamp.digicert.com).
    RFC3161_TSA_URL: str = os.getenv("RFC3161_TSA_URL", "")
    RFC3161_TIMEOUT_SECONDS: int = int(os.getenv("RFC3161_TIMEOUT_SECONDS", "10"))
    # Optional: the TSA's CA cert (and, if it signs with an intermediate,
    # that intermediate) for full chain verification via openssl ts -verify.
    # Without these, verification still checks the token's internal
    # signature is self-consistent, just not chained to a trusted root.
    RFC3161_TSA_CA_CERT_PATH: str = os.getenv("RFC3161_TSA_CA_CERT_PATH", "")
    RFC3161_TSA_UNTRUSTED_CERT_PATH: str = os.getenv("RFC3161_TSA_UNTRUSTED_CERT_PATH", "")

    # Multi-party checkpoint witnessing (app/integrity/witness.py). A
    # comma-separated allowlist of hex Ed25519 public keys this instance will
    # accept an externally-submitted witness cosignature from. Empty by
    # default -- no external party is configured, so only the local second
    # key (still real, still a second signature) witnesses by default.
    WITNESS_TRUSTED_PUBLIC_KEYS: str = os.getenv("WITNESS_TRUSTED_PUBLIC_KEYS", "")
    # If true, every newly-created checkpoint is automatically cosigned by
    # this instance's own local witness key at creation time (no extra API
    # call needed). External witnessing is always opt-in via its own endpoint.
    AUTO_WITNESS_LOCAL: bool = os.getenv("AUTO_WITNESS_LOCAL", "true").lower() == "true"

    class Config:
        case_sensitive = True

settings = Settings()
