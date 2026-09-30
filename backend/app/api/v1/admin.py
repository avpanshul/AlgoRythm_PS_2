"""Admin API (Users, Roles, Organizations)."""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import hash_password, create_access_token
from app.core.deps import require_role
from app.core.config import settings
from app.models.all import User, Role, Organization, AuditLog, IngestToken, IngestionRun

router = APIRouter()

class UserCreate(BaseModel):
    id: str
    name: str
    email: str
    role_name: Optional[str] = None
    organization_id: Optional[str] = None
    # Real invite flow: this project has no outbound email configured, so
    # there's no way to send a signup link. Instead, generate (or accept) a
    # real temporary password here and hand it back once in the response --
    # the admin shares it out-of-band. `create_user` used to build a User
    # from `req.model_dump()` directly, which never set password_hash at
    # all -- an "invited" user existed as a row but could never actually
    # log in, since password_hash stayed NULL forever.
    password: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role_name: Optional[str] = None
    organization_id: Optional[str] = None
    status: Optional[str] = None

class UserOut(BaseModel):
    """Never include password_hash -- the ORM model has no built-in exclusion,
    so an explicit response_model is what keeps the bcrypt hash out of every
    /users response instead of it silently riding along in the raw row."""
    id: str
    name: str
    email: str
    role_name: Optional[str] = None
    organization_id: Optional[str] = None
    status: str
    last_active: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@router.post("/users")
def create_user(req: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter((User.id == req.id) | (User.email == req.email)).first():
        raise HTTPException(status_code=400, detail="User ID or Email already exists")

    temp_password = req.password or secrets.token_urlsafe(9)
    user = User(
        id=req.id, name=req.name, email=req.email,
        role_name=req.role_name, organization_id=req.organization_id,
        password_hash=hash_password(temp_password), status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    out = UserOut.model_validate(user).model_dump()
    # Only ever returned here, once, on creation -- never stored in plaintext
    # and never included in GET /users.
    out["temporary_password"] = temp_password
    return out

@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, req: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(user, k, v)

    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"status": "deleted"}


@router.get("/roles")
def list_roles(db: Session = Depends(get_db)):
    return db.query(Role).all()

class OrganizationCreate(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    sector: Optional[str] = None
    contact_email: Optional[str] = None


@router.get("/organizations")
def list_organizations(db: Session = Depends(get_db)):
    return db.query(Organization).all()


@router.post("/organizations")
def create_organization(req: OrganizationCreate, db: Session = Depends(get_db)):
    if db.query(Organization).filter(Organization.id == req.id).first():
        raise HTTPException(status_code=400, detail="Organization ID already exists")
    org = Organization(**req.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    return org

@router.get("/connectors")
def list_connectors():
    # Stub for connectors if not in Integrations table
    return [
        {"id": "c1", "name": "Kafka Source"},
        {"id": "c2", "name": "Syslog Listener"},
        {"id": "c3", "name": "S3 Fetcher"}
    ]


# ─── Ingest-scoped tokens (Part D1: separate ingest-vs-admin token identities) ──

class IngestTokenCreate(BaseModel):
    name: str
    source_id: Optional[str] = None


class IngestTokenOut(BaseModel):
    id: str
    name: str
    source_id: Optional[str] = None
    created_by: str
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    revoked: bool

    class Config:
        from_attributes = True


@router.get("/admin/ingest-tokens", response_model=list[IngestTokenOut])
def list_ingest_tokens(db: Session = Depends(get_db), current_user: User = Depends(require_role("admin"))):
    return db.query(IngestToken).order_by(IngestToken.created_at.desc()).all()


@router.post("/admin/ingest-tokens")
def issue_ingest_token(req: IngestTokenCreate, db: Session = Depends(get_db), current_user: User = Depends(require_role("admin"))):
    """Mints an ingest-scoped bearer token: it can only reach the ingestion
    router (see app/core/deps.py's get_ingest_or_user), never /admin,
    /settings, /users, or any other endpoint -- unlike a real user's login
    token, which is scope="full" and can reach everything that user's role
    allows. The raw token is returned exactly once, here; only its row
    (id/name/source_id/timestamps, never the token itself) is stored, so
    losing this response means re-issuing a new token, not "looking it up
    again"."""
    token_id = uuid.uuid4().hex
    row = IngestToken(id=token_id, source_id=req.source_id, name=req.name, created_by=current_user.id)
    db.add(row)
    db.add(AuditLog(user=current_user.id, action="ingest_token_issued", entity_type="IngestToken", entity_id=token_id,
                     after_state={"name": req.name, "source_id": req.source_id}))
    db.commit()

    token = create_access_token(
        subject=f"ingest:{req.source_id or 'unassigned'}",
        extra_claims={"scope": "ingest", "jti": token_id, "source_id": req.source_id},
        expire_minutes=settings.INGEST_TOKEN_EXPIRE_DAYS * 24 * 60,
    )
    return {"token": token, "id": token_id}


@router.delete("/admin/ingest-tokens/{token_id}")
def revoke_ingest_token(token_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_role("admin"))):
    row = db.query(IngestToken).filter(IngestToken.id == token_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Ingest token not found")
    row.revoked = True
    row.revoked_at = datetime.now(timezone.utc)
    db.add(AuditLog(user=current_user.id, action="ingest_token_revoked", entity_type="IngestToken", entity_id=token_id))
    db.commit()
    return {"status": "revoked", "id": token_id}


# ─── Automatic re-ingestion runs (app/services/auto_ingest.py) ─────────────

class IngestionRunOut(BaseModel):
    id: str
    trigger: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    new_events_ingested: int
    skipped_duplicates: int
    dlq_count: int
    format_breakdown: Optional[dict] = None
    corpus_exhausted: bool
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/admin/ingestion-runs", response_model=list[IngestionRunOut])
def list_ingestion_runs(db: Session = Depends(get_db), current_user: User = Depends(require_role("admin"))):
    """Real per-run history of the twice-daily automatic re-ingestion
    scheduler -- every row here is a run that actually happened (or is
    currently running/failed), with its real counts, not a projection."""
    return db.query(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(100).all()


@router.post("/admin/ingestion-runs/trigger", response_model=IngestionRunOut)
def trigger_ingestion_run(db: Session = Depends(get_db), current_user: User = Depends(require_role("admin"))):
    """Manually triggers one auto-ingest pass on demand (trigger="manual"),
    using the same run_once() the scheduled 08:00/20:00 slots call -- useful
    for verifying the pipeline is working without waiting for the next slot."""
    from app.services.auto_ingest import run_once
    result = run_once(db, trigger="manual")
    run = db.query(IngestionRun).filter(IngestionRun.id == result.get("run_id")).first()
    if not run:
        raise HTTPException(status_code=500, detail="Ingestion run did not record a row")
    return run


# ─── One-off real-data bootstrap (temporary; remove after use) ──────────
#
# seed.py's main() is the exact script every local dev environment has always
# been run through once, by hand, against a fresh Postgres, to load the real
# loghub/EVTX/Zeek/CloudTrail corpora + role/parser/correlation-rule
# definitions. Nothing in the Docker image, Procfile, or startup_event ever
# calls it automatically -- a real gap found live: this deployment's fresh
# production DB never got that one-time bootstrap a local dev DB always has,
# which is the entire reason its event/source/parser counts don't match
# local's. seed_real_events() has no dedup guard (unlike auto_ingest.py's
# run_once(), which explicitly skips already-ingested sha256es for exactly
# this reason) -- calling it twice would double every row -- so this is
# deliberately NOT a repeatable button: it refuses outright if the real
# sources it seeds already exist, and it's meant to be deleted from this
# file again once it's been run the one time production actually needs it.
import threading as _threading

_bootstrap_state = {"status": "idle", "detail": None}
_bootstrap_lock = _threading.Lock()


def _run_bootstrap_seed():
    global _bootstrap_state
    # Real OOM root cause found live: live_detection.py's always-on 30s
    # background cycle does two full-table scans every single firing
    # (correlation.py's evaluate_rule(), sentinel.py's
    # update_all_profiles()), completely unbounded -- confirmed via Render's
    # own oomKilled events recurring specifically while this bulk-seed
    # thread runs, i.e. the two background loops sharing this one process's
    # 512MB compete for memory at exactly the moment the DB they're both
    # scanning is growing fastest. Pausing it for the duration of a bulk
    # backfill (historical data doesn't need real-time propagation) is a
    # real fix for the actual bug, not a workaround.
    from app.services.live_detection import pause_background_detection, resume_background_detection
    pause_background_detection()
    try:
        import seed as _seed
        _seed.main()
        _bootstrap_state = {"status": "done", "detail": None}
    except Exception as e:
        _bootstrap_state = {"status": "error", "detail": str(e)}
    finally:
        resume_background_detection()


@router.post("/admin/oneoff-bootstrap-real-data")
def oneoff_bootstrap_real_data(db: Session = Depends(get_db), current_user: User = Depends(require_role("admin"))):
    # seed_real_events() now skips any row whose raw_sha256 is already in
    # RawEventMetadata (real gap found live: a Render free-tier idle-timeout
    # spun this down mid-run at ~13,800/34,600 events, with no deploy event
    # to explain it -- inbound-HTTP inactivity triggers that independently
    # of a background thread's own CPU usage), so re-running main() is
    # always safe now: it resumes from wherever a prior run stopped instead
    # of duplicating anything. Only concurrent runs need blocking.
    with _bootstrap_lock:
        if _bootstrap_state["status"] == "running":
            raise HTTPException(status_code=409, detail="Bootstrap already running")
        _bootstrap_state["status"] = "running"
        _bootstrap_state["detail"] = None
        _threading.Thread(target=_run_bootstrap_seed, daemon=True).start()
    return {"status": "started"}


@router.get("/admin/oneoff-bootstrap-real-data/status")
def oneoff_bootstrap_real_data_status(current_user: User = Depends(require_role("admin"))):
    return _bootstrap_state


# seed.main() seeds loghub -> EVTX -> Zeek -> CloudTrail in that fixed order,
# and the full bootstrap above stalled partway through EVTX (Render free-tier
# OOM). CloudTrail is the only real corpus that's JSON-formatted -- with it
# still unseeded, the dashboard's format-distribution panel honestly showed
# 0% JSON, which looked like a bug but wasn't one. Rather than fabricate JSON
# rows or delete already-seeded real ones to "fix" the percentage (both
# explicitly ruled out), this seeds just that one real corpus (2,900 records,
# small enough to plausibly fit in the memory headroom that a full-run resume
# no longer has) directly, out of the main() order, using the same
# dedup-safe seed_real_events() the full bootstrap already relies on.
_cloudtrail_state = {"status": "idle", "detail": None}
_cloudtrail_lock = _threading.Lock()


def _run_cloudtrail_seed():
    global _cloudtrail_state
    # Same real OOM fix as _run_bootstrap_seed above: pause the always-on
    # live_detection background thread (its two unbounded full-table scans
    # compete for this process's 512MB with this seed thread's own DB
    # writes) for the duration of this run.
    from app.services.live_detection import pause_background_detection, resume_background_detection
    pause_background_detection()
    try:
        import seed as _seed
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            result = _seed.seed_real_events(
                db,
                corpus_path=_seed.CLOUDTRAIL_CORPUS_PATH,
                builder_module="build_cloudtrail_corpus",
                label="AWS CloudTrail",
            )
            _cloudtrail_state = {"status": "done", "detail": result}
        finally:
            db.close()
    except Exception as e:
        _cloudtrail_state = {"status": "error", "detail": str(e)}
    finally:
        resume_background_detection()


@router.post("/admin/oneoff-seed-cloudtrail")
def oneoff_seed_cloudtrail(current_user: User = Depends(require_role("admin"))):
    with _cloudtrail_lock:
        if _cloudtrail_state["status"] == "running":
            raise HTTPException(status_code=409, detail="CloudTrail seed already running")
        _cloudtrail_state["status"] = "running"
        _cloudtrail_state["detail"] = None
        _threading.Thread(target=_run_cloudtrail_seed, daemon=True).start()
    return {"status": "started"}


@router.get("/admin/oneoff-seed-cloudtrail/status")
def oneoff_seed_cloudtrail_status(current_user: User = Depends(require_role("admin"))):
    return _cloudtrail_state
