from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from alembic import command
from alembic.config import Config as AlembicConfig

from app.core.config import settings
from app.api.v1 import ingestion, events, mappings, sources, analytics, pipeline, dlq, replay, audit, analytics_ts, rules, parsers_api, storage_api, admin, integrations_api, threat_intel
from app.core.storage import init_minio
from app.core.search import init_opensearch

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Universal Log Pre-processing Framework for SIH26156",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    # Run database migrations
    try:
        alembic_ini = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
        alembic_cfg = AlembicConfig(alembic_ini)
        command.upgrade(alembic_cfg, "head")
        print("Database migrations applied.")
    except Exception as e:
        print(f"DB migration warning: {e}")

    # MinIO and OpenSearch are not used in PostgreSQL demo mode,
    # but we can try to initialize them just in case they are up.
    try:
        init_minio()
        print("MinIO initialized.")
    except Exception as e:
        print(f"MinIO init warning (expected in demo mode): {e}")

    try:
        init_opensearch()
        print("OpenSearch initialized.")
    except Exception as e:
        print(f"OpenSearch init warning (expected in demo mode): {e}")

# Register routers
app.include_router(ingestion.router, prefix=settings.API_V1_STR, tags=["Ingestion"])
app.include_router(events.router, prefix=settings.API_V1_STR, tags=["Events"])
app.include_router(mappings.router, prefix=settings.API_V1_STR, tags=["Mappings"])
app.include_router(sources.router, prefix=settings.API_V1_STR, tags=["Sources"])
app.include_router(analytics.router, prefix=settings.API_V1_STR, tags=["Analytics"])
app.include_router(pipeline.router, prefix=settings.API_V1_STR, tags=["Pipeline"])
app.include_router(dlq.router, prefix=settings.API_V1_STR, tags=["DLQ"])
app.include_router(replay.router, prefix=settings.API_V1_STR, tags=["Replay"])
app.include_router(audit.router, prefix=settings.API_V1_STR, tags=["Audit"])
app.include_router(analytics_ts.router, prefix=settings.API_V1_STR, tags=["Analytics TS"])
app.include_router(rules.router, prefix=settings.API_V1_STR, tags=["Rules"])
app.include_router(parsers_api.router, prefix=settings.API_V1_STR, tags=["Parsers"])
app.include_router(storage_api.router, prefix=settings.API_V1_STR, tags=["Storage"])
app.include_router(admin.router, prefix=settings.API_V1_STR, tags=["Admin"])
app.include_router(integrations_api.router, prefix=settings.API_V1_STR, tags=["Integrations"])
app.include_router(threat_intel.router, prefix=settings.API_V1_STR, tags=["Threat Intel"])

@app.get(f"{settings.API_V1_STR}/health")
def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "project": settings.PROJECT_NAME
    }
