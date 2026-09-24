"""Replay jobs CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.all import ReplayJob, AuditLog

router = APIRouter()


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
def create_replay_job(req: CreateReplayJobRequest, db: Session = Depends(get_db)):
    job = ReplayJob(
        name=req.name or f"Replay-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        source_id=req.source_id,
        time_range_start=req.time_range_start,
        time_range_end=req.time_range_end,
        old_parser_version=req.old_parser_version,
        new_parser_version=req.new_parser_version,
        requested_by=req.requested_by,
        status="pending",
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
    
    # In a real system, this would trigger a background task. 
    # For demo, we leave it as pending.
    
    return job


@router.get("/replay/jobs/{job_id}")
def get_replay_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ReplayJob).filter(ReplayJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Replay job not found")
    return job


@router.post("/replay/jobs/{job_id}/approve")
def approve_replay_job(job_id: int, approved_by: str = Query("admin"), db: Session = Depends(get_db)):
    job = db.query(ReplayJob).filter(ReplayJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Replay job not found")
    
    if job.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Cannot approve job in status {job.status}")
        
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
    
    return {"status": "approved", "job_id": job_id}
