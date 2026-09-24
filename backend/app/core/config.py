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

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Kafka / Redpanda
    KAFKA_BROKERS: str = os.getenv("KAFKA_BROKERS", "localhost:9092")

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
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "phi3:mini")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    
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
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")

    # Logic Configuration
    RISK_WEIGHTS: dict = json.loads(os.getenv("RISK_WEIGHTS", '{"severity": 0.3, "action": 0.2, "frequency": 0.2, "asset": 0.15, "correlation": 0.15}'))
    CONFIDENCE_THRESHOLDS: dict = json.loads(os.getenv("CONFIDENCE_THRESHOLDS", '{"auto_approve": 0.90, "review": 0.70}'))

    AIRGAPPED_MODE: bool = os.getenv("AIRGAPPED_MODE", "true").lower() == "true"

    class Config:
        case_sensitive = True

settings = Settings()
