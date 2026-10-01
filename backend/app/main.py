from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import traceback
from alembic import command
from alembic.config import Config as AlembicConfig

from app.core.config import settings
from app.core.deps import get_current_user, get_ingest_or_user
from app.api.v1 import ingestion, events, mappings, sources, analytics, pipeline, dlq, replay, audit, analytics_ts, rules, parsers_api, storage_api, admin, integrations_api, threat_intel, auth, integrity, supervisory, evidence, export, privacy_policies, correlations, entities, cases, retention, graph, hunts, unknown_clusters, pack_sharing, settings_api, sparks
from app.services.live_detection import start_background_detection
from app.services.auto_ingest import start_auto_ingest
from app.workers.checkpoint_scheduler import start_background_reverification
from app.core.storage import init_minio
from app.core.search import init_opensearch
from app.core.security_middleware import rate_limit_middleware, security_headers_middleware, csrf_middleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Universal Log Pre-processing Framework for SIH26156",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Explicit origin allowlist -- "*" + allow_credentials=True is both spec-invalid
# (browsers reject it) and a real anti-pattern if any client tolerates it.
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Real gap found live on the Render deployment: an unhandled exception inside
# a route returned Starlette's default plain-text 500 with zero trace in
# Render's log stream -- its own request-scope stderr write isn't reliably
# captured there (confirmed: the startup-crash Alembic traceback earlier had
# the exact same gap). print() to stdout is reliably captured, so every
# unhandled exception is now logged that way before the generic 500 goes out.
@app.exception_handler(Exception)
async def _log_unhandled_exception(request: Request, exc: Exception):
    print(f"UNHANDLED EXCEPTION on {request.method} {request.url.path}: {exc!r}", flush=True)
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Request body size guard, mainly for the raw-body /ingest/syslog endpoint which
# reads request.body() directly and has no Pydantic-level size validation.
# Applies to every request as a general defense-in-depth backstop.
MAX_REQUEST_BODY_BYTES = 5 * 1024 * 1024  # 5 MB


@app.middleware("http")
async def limit_request_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body too large (max {MAX_REQUEST_BODY_BYTES} bytes)"},
                )
        except ValueError:
            pass
    return await call_next(request)


# Registered after the body-size guard so it wraps outermost (Starlette runs
# the most-recently-added @app.middleware first on the way in) -- rate
# limiting and security headers apply even to a 413 from the guard above.
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)
app.middleware("http")(csrf_middleware)


@app.on_event("startup")
def startup_event():
    # Run database migrations. Deliberately NOT caught-and-continued: a real
    # live-cluster smoke test found that swallowing this exception let the
    # app report itself healthy/ready with a completely empty database (the
    # migration failed, but every subsequent request -- including the
    # readiness probe, which doesn't touch the DB -- looked fine). A broken
    # migration must fail startup loudly so Kubernetes shows CrashLoopBackOff
    # with the real error, not silently serve traffic against no schema.
    alembic_ini = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    alembic_cfg = AlembicConfig(alembic_ini)
    command.upgrade(alembic_cfg, "head")
    print("Database migrations applied.")

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

    # Seed an initial admin user (idempotent, opt-in via ADMIN_INITIAL_PASSWORD).
    # No hardcoded password is ever used -- if the env var isn't set, no account
    # is created and an operator must create one via POST /api/v1/users directly
    # against the DB, or by setting ADMIN_INITIAL_PASSWORD and restarting.
    try:
        from app.core.database import SessionLocal
        from app.core.security import hash_password
        from app.models.all import User, Role

        if settings.ADMIN_INITIAL_PASSWORD:
            db = SessionLocal()
            try:
                existing = db.query(User).filter(User.email == settings.ADMIN_INITIAL_EMAIL).first()
                if not existing:
                    if not db.query(Role).filter(Role.name == "admin").first():
                        db.add(Role(name="admin", description="Full administrative access", permissions=["*"]))
                        db.commit()
                    db.add(User(
                        id="admin",
                        name="Administrator",
                        email=settings.ADMIN_INITIAL_EMAIL,
                        role_name="admin",
                        status="active",
                        password_hash=hash_password(settings.ADMIN_INITIAL_PASSWORD),
                    ))
                    db.commit()
                    print(f"Seeded initial admin user ({settings.ADMIN_INITIAL_EMAIL}).")
                else:
                    print("Admin seed skipped: user with ADMIN_INITIAL_EMAIL already exists.")
            finally:
                db.close()
        else:
            print("ADMIN_INITIAL_PASSWORD not set -- skipping admin seed. Set it and restart to bootstrap an account.")
    except Exception as e:
        print(f"Admin seed warning (expected if DB is unreachable in demo mode): {e}")

    # Real-time attack propagation (E2/E8 audit gap): run correlation +
    # Sentinel continuously in the background rather than only on a manual
    # POST /correlations/evaluate click -- see app/services/live_detection.py.
    start_background_detection(interval_seconds=30)
    print("Live detection background cycle started (30s interval).")

    # Twice-daily automatic real-data re-ingestion (app/services/auto_ingest.py).
    start_auto_ingest()

    # Scheduled checkpoint self-verification (app/workers/checkpoint_scheduler.py).
    start_background_reverification()

# Auth (login is intentionally open -- you need it before you have a token)
app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["Auth"])

# Register routers.
#
# `dependencies=[Depends(get_current_user)]` requires a valid bearer token for every
# route in that router. Applied at include_router() time (rather than per-route) for
# routers that are sensitive end-to-end: they write data, expose PII/secrets-adjacent
# config, or drive destructive/administrative actions.
#
# Left OPEN (no auth) as a deliberate demo/read-only call:
#   - events, analytics, analytics_ts, pipeline, parsers_api, storage_api, sources,
#     threat_intel: GET-heavy dashboard/analytics surfaces intended to back a public-ish
#     read view of the SIEM for this demo. `sources` also has a POST; left open here
#     because source registration carries no secret and the assignment didn't call it
#     out -- flagged in the report as a candidate to lock down before real deployment.
#
# Protected (router-wide): admin (users/roles/orgs), audit, dlq, rules, integrations,
# ingestion (writes raw logs to disk/DB -- also gets the size-limit + validation fixes).
#
# Protected (per-route only, see mappings.py / replay.py): mappings approve/reject,
# replay job approval -- their GET/list endpoints stay open per the read-only carve-out,
# only the state-changing approve/reject/approval actions require a token.
app.include_router(ingestion.router, prefix=settings.API_V1_STR, tags=["Ingestion"], dependencies=[Depends(get_ingest_or_user)])
app.include_router(events.router, prefix=settings.API_V1_STR, tags=["Events"])
app.include_router(mappings.router, prefix=settings.API_V1_STR, tags=["Mappings"])
app.include_router(sources.router, prefix=settings.API_V1_STR, tags=["Sources"])
app.include_router(analytics.router, prefix=settings.API_V1_STR, tags=["Analytics"])
app.include_router(pipeline.router, prefix=settings.API_V1_STR, tags=["Pipeline"])
app.include_router(dlq.router, prefix=settings.API_V1_STR, tags=["DLQ"], dependencies=[Depends(get_current_user)])
app.include_router(replay.router, prefix=settings.API_V1_STR, tags=["Replay"])
app.include_router(audit.router, prefix=settings.API_V1_STR, tags=["Audit"], dependencies=[Depends(get_current_user)])
app.include_router(analytics_ts.router, prefix=settings.API_V1_STR, tags=["Analytics TS"])
app.include_router(rules.router, prefix=settings.API_V1_STR, tags=["Rules"], dependencies=[Depends(get_current_user)])
app.include_router(parsers_api.router, prefix=settings.API_V1_STR, tags=["Parsers"], dependencies=[Depends(get_current_user)])
app.include_router(storage_api.router, prefix=settings.API_V1_STR, tags=["Storage"])
app.include_router(admin.router, prefix=settings.API_V1_STR, tags=["Admin"], dependencies=[Depends(get_current_user)])
app.include_router(integrations_api.router, prefix=settings.API_V1_STR, tags=["Integrations"], dependencies=[Depends(get_current_user)])
app.include_router(settings_api.router, prefix=settings.API_V1_STR, tags=["Settings"])
app.include_router(threat_intel.router, prefix=settings.API_V1_STR, tags=["Threat Intel"])
app.include_router(integrity.router, prefix=settings.API_V1_STR, tags=["Integrity"])
app.include_router(supervisory.router, prefix=settings.API_V1_STR, tags=["Supervisory"], dependencies=[Depends(get_current_user)])
app.include_router(evidence.router, prefix=settings.API_V1_STR, tags=["Evidence"])
app.include_router(export.router, prefix=settings.API_V1_STR, tags=["Export"])
app.include_router(privacy_policies.router, prefix=settings.API_V1_STR, tags=["Privacy"], dependencies=[Depends(get_current_user)])
app.include_router(correlations.router, prefix=settings.API_V1_STR, tags=["Correlation"])
app.include_router(entities.router, prefix=settings.API_V1_STR, tags=["Entities"])
app.include_router(cases.router, prefix=settings.API_V1_STR, tags=["Cases"])
app.include_router(retention.router, prefix=settings.API_V1_STR, tags=["Retention"])
app.include_router(graph.router, prefix=settings.API_V1_STR, tags=["Graph"])
app.include_router(hunts.router, prefix=settings.API_V1_STR, tags=["Hunts"])
app.include_router(unknown_clusters.router, prefix=settings.API_V1_STR, tags=["Unknown Clusters"], dependencies=[Depends(get_current_user)])
app.include_router(pack_sharing.router, prefix=settings.API_V1_STR, tags=["Pack Sharing"], dependencies=[Depends(get_current_user)])
app.include_router(sparks.router, prefix=settings.API_V1_STR, tags=["Sparks"])

@app.get(f"{settings.API_V1_STR}/health")
def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "project": settings.PROJECT_NAME
    }
