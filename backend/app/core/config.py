import os
import json
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Universal Log Pre-processing Framework"
    API_V1_STR: str = "/api/v1"
    
    # Postgres
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "ulp")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "ulp_password")
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
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "password123")
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
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-key-change-in-production")
    
    # Logic Configuration
    RISK_WEIGHTS: dict = json.loads(os.getenv("RISK_WEIGHTS", '{"severity": 0.3, "action": 0.2, "frequency": 0.2, "asset": 0.15, "correlation": 0.15}'))
    CONFIDENCE_THRESHOLDS: dict = json.loads(os.getenv("CONFIDENCE_THRESHOLDS", '{"auto_approve": 0.90, "review": 0.70}'))

    AIRGAPPED_MODE: bool = os.getenv("AIRGAPPED_MODE", "true").lower() == "true"

    class Config:
        case_sensitive = True

settings = Settings()
