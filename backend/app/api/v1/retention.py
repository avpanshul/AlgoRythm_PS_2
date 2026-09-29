"""Retention and legal hold API (ULPF-master-prompt.md D10)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.retention import place_hold, release_hold, delete_event, run_retention_sweep
from app.models.all import RetentionPolicy, LegalHold, Source, User

router = APIRouter()


class RetentionPolicyIn(BaseModel):
    source_id: str
    retention_days: int
    enabled: bool = True


class HoldCreate(BaseModel):
    source_id: str
    reason: str


@router.get("/retention-policies")
def list_policies(db: Session = Depends(get_db)):
    return [_policy_out(p) for p in db.query(RetentionPolicy).all()]


@router.put("/retention-policies")
def upsert_policy(req: RetentionPolicyIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if req.retention_days < 1:
        raise HTTPException(status_code=400, detail="retention_days must be positive")
    if not db.query(Source).filter(Source.id == req.source_id).first():
        raise HTTPException(status_code=404, detail="source_id does not reference an existing source")

    policy = db.query(RetentionPolicy).filter(RetentionPolicy.source_id == req.source_id).first()
    if policy:
        policy.retention_days = req.retention_days
        policy.enabled = req.enabled
    else:
        policy = RetentionPolicy(source_id=req.source_id, retention_days=req.retention_days, enabled=req.enabled)
        db.add(policy)
    db.commit()
    db.refresh(policy)
    return _policy_out(policy)


@router.get("/legal-holds")
def list_holds(source_id: Optional[str] = None, active_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(LegalHold)
    if source_id:
        q = q.filter(LegalHold.source_id == source_id)
    if active_only:
        q = q.filter(LegalHold.released_at.is_(None))
    return [_hold_out(h) for h in q.order_by(LegalHold.created_at.desc()).all()]


@router.post("/legal-holds")
def create_hold(req: HoldCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not db.query(Source).filter(Source.id == req.source_id).first():
        raise HTTPException(status_code=404, detail="source_id does not reference an existing source")
    hold = place_hold(db, req.source_id, req.reason, current_user.id)
    return _hold_out(hold)


@router.post("/legal-holds/{hold_id}/release")
def release_hold_endpoint(hold_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    hold = release_hold(db, hold_id, current_user.id)
    if not hold:
        raise HTTPException(status_code=404, detail="Legal hold not found")
    return _hold_out(hold)


@router.delete("/events/{event_id}")
def delete_event_endpoint(event_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = delete_event(db, event_id, current_user.id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Event not found")
    if result["status"] == "blocked":
        raise HTTPException(status_code=403, detail=result["reason"])
    return result


@router.post("/retention/run-sweep")
def trigger_sweep(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return run_retention_sweep(db)


def _policy_out(p: RetentionPolicy) -> dict:
    return {"source_id": p.source_id, "retention_days": p.retention_days, "enabled": p.enabled}


def _hold_out(h: LegalHold) -> dict:
    return {
        "id": h.id, "source_id": h.source_id, "reason": h.reason, "created_by": h.created_by,
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "released_at": h.released_at.isoformat() if h.released_at else None,
        "released_by": h.released_by,
    }
