"""Replay jobs: re-run corrected parsers against untouched raw evidence.

A replay job re-parses raw logs already sitting in the vault (bronze tier)
using a newer published parser version, and produces new NormalizedEvent rows.
The raw bytes and their SHA-256 are never touched or recomputed -- only the
normalized (silver) output changes, and the new normalized_sha256 + Merkle leaf
are appended fresh, so history isn't rewritten, it's extended."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from app.core.database import get_db, SessionLocal
from app.core.deps import get_current_user
from app.core.local_storage import read_raw_log
from app.core.processing import process_raw_event
from app.models.all import ReplayJob, RawEventMetadata, AuditLog, User, NormalizedEvent, NormalizedEventVersion

router = APIRouter()


def _run_replay_job(job_id: int):
    """Runs in a background task: re-parses every raw event matching the job's
    filters and re-normalizes it. Isolated DB session since this outlives the
    request that triggered it."""
    db = SessionLocal()
    try:
        job = db.query(ReplayJob).filter(ReplayJob.id == job_id).first()
        if not job:
            return
        job.status = "running"
        db.commit()

        query = db.query(RawEventMetadata)
        if job.source_id:
            query = query.filter(RawEventMetadata.source_id == job.source_id)
        if job.time_range_start:
            query = query.filter(RawEventMetadata.received_at >= job.time_range_start)
        if job.time_range_end:
            query = query.filter(RawEventMetadata.received_at <= job.time_range_end)

        raw_events = query.order_by(RawEventMetadata.received_at.asc()).all()
        job.total_events = len(raw_events)
        db.commit()

        processed = 0
        changed = 0
        for meta in raw_events:
            try:
                raw_content = read_raw_log(meta.raw_location)
            except Exception:
                processed += 1
                continue

            before = db.query(NormalizedEvent).filter(NormalizedEvent.event_id == meta.event_id).first()
            before_hash = before.normalized_sha256 if before else None

            # Real fix (was: replay silently overwrote NormalizedEvent in
            # place, losing the prior normalization entirely -- "append new
            # versions, never overwrite" violated in exactly this one spot).
            # Archive the pre-replay snapshot before it's replaced.
            if before:
                db.add(NormalizedEventVersion(
                    event_id=before.event_id,
                    superseded_by_replay_job_id=job.id,
                    event_data=before.event_data,
                    source_ip=before.source_ip,
                    dest_ip=before.dest_ip,
                    user_name=before.user_name,
                    parser_id=before.parser_id,
                    parser_version=before.parser_version,
                    mapping_method=before.mapping_method,
                    risk_score=before.risk_score,
                    risk_level=before.risk_level,
                    normalized_sha256=before.normalized_sha256,
                    canonical_json=before.canonical_json,
                ))
                db.commit()

            # Untouched raw evidence in, corrected parser out -- raw_sha256 and
            # raw_location are passed straight through, never recomputed.
            process_raw_event(
                db, meta.event_id, raw_content, meta.source_id or "UNKNOWN",
                meta.raw_sha256, meta.raw_location,
                parser_version=job.new_parser_version,
            )
            db.commit()

            after = db.query(NormalizedEvent).filter(NormalizedEvent.event_id == meta.event_id).first()
            after_hash = after.normalized_sha256 if after else None
            if after_hash != before_hash:
                changed += 1

            processed += 1
            job.processed_events = processed
            job.changed_events = changed
            job.progress = int(processed / job.total_events * 100) if job.total_events else 100
            db.commit()

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.add(AuditLog(
            user=job.requested_by or "system",
            action="replay_job_completed",
            entity_type="ReplayJob",
            entity_id=str(job.id),
            after_state={"processed": processed, "changed": changed, "total": job.total_events},
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        job = db.query(ReplayJob).filter(ReplayJob.id == job_id).first()
        if job:
            job.status = "failed"
            db.add(AuditLog(
                user="system", action="replay_job_failed", entity_type="ReplayJob",
                entity_id=str(job_id), after_state={"error": str(e)[:500]},
            ))
            db.commit()
    finally:
        db.close()


class CreateReplayJobRequest(BaseModel):
    name: Optional[str] = None
    source_id: Optional[str] = None
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None
    old_parser_version: Optional[str] = None
    new_parser_version: Optional[str] = None
    requested_by: Optional[str] = None


@router.get("/replay/jobs")
def list_replay_jobs(
    status: Optional[str] = None,
    source_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(ReplayJob)
    if status:
        q = q.filter(ReplayJob.status == status)
    if source_id:
        q = q.filter(ReplayJob.source_id == source_id)

    total = q.count()
    items = q.order_by(ReplayJob.created_at.desc()).offset((page - 1) * size).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": j.id,
                "name": j.name,
                "source_id": j.source_id,
                "status": j.status,
                "progress": j.progress,
                "total_events": j.total_events,
                "processed_events": j.processed_events,
                "changed_events": j.changed_events,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in items
        ],
    }


@router.post("/replay/jobs")
def create_replay_job(req: CreateReplayJobRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = ReplayJob(
        name=req.name or f"Replay-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        source_id=req.source_id,
        time_range_start=req.time_range_start,
        time_range_end=req.time_range_end,
        old_parser_version=req.old_parser_version,
        new_parser_version=req.new_parser_version,
        requested_by=req.requested_by,
        # A parser-version change is applied via /approve first (separation of
        # duties: the requester isn't the approver); a plain backlog re-parse with
        # no version bump can run immediately.
        status="pending_approval" if req.new_parser_version else "pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    audit = AuditLog(
        user=req.requested_by or "system",
        action="replay_job_created",
        entity_type="ReplayJob",
        entity_id=str(job.id),
    )
    db.add(audit)
    db.commit()

    if job.status == "pending":
        background_tasks.add_task(_run_replay_job, job.id)

    return job


@router.post("/replay/jobs/{job_id}/run")
def run_replay_job(job_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(ReplayJob).filter(ReplayJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Replay job not found")
    if job.status not in ("pending", "approved"):
        raise HTTPException(status_code=400, detail=f"Cannot run job in status {job.status}")

    background_tasks.add_task(_run_replay_job, job.id)
    return {"status": "started", "job_id": job_id}


@router.get("/replay/jobs/{job_id}")
def get_replay_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ReplayJob).filter(ReplayJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Replay job not found")
    return job


@router.post("/replay/jobs/{job_id}/approve")
def approve_replay_job(job_id: int, background_tasks: BackgroundTasks, approved_by: str = Query("admin"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(ReplayJob).filter(ReplayJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Replay job not found")

    if job.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Cannot approve job in status {job.status}")

    if job.requested_by and job.requested_by == approved_by:
        raise HTTPException(status_code=400, detail="Requester cannot approve their own replay job")

    job.status = "approved"
    job.approved_by = approved_by

    audit = AuditLog(
        user=approved_by,
        action="replay_job_approved",
        entity_type="ReplayJob",
        entity_id=str(job_id),
    )
    db.add(audit)
    db.commit()

    background_tasks.add_task(_run_replay_job, job.id)

    return {"status": "approved", "job_id": job_id}
