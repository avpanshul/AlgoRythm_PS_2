"""Threat-hunting workspace: saved queries + audited execution
(ULPF-phase2-prompt.md E3). Pivoting itself is served by GET /graph?entity=
(app/api/v1/graph.py) -- one click from any IP field reuses the same entity
graph E2 built, rather than a second, parallel pivot mechanism.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.all import SavedQuery, AuditLog, User, NormalizedEvent

router = APIRouter()


class SavedQueryCreate(BaseModel):
    name: str
    filter: dict


@router.get("/hunts")
def list_saved_queries(db: Session = Depends(get_db)):
    queries = db.query(SavedQuery).order_by(SavedQuery.created_at.desc()).all()
    return [_out(q) for q in queries]


@router.post("/hunts")
def create_saved_query(req: SavedQueryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = SavedQuery(id=f"query-{uuid.uuid4().hex[:16]}", name=req.name, filter=req.filter, owner=current_user.id)
    db.add(q)
    db.commit()
    db.refresh(q)
    return _out(q)


@router.delete("/hunts/{query_id}")
def delete_saved_query(query_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(SavedQuery).filter(SavedQuery.id == query_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Saved query not found")
    db.delete(q)
    db.commit()
    return {"status": "deleted"}


@router.post("/hunts/{query_id}/run")
def run_saved_query(query_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Executes a saved query and audit-logs the run -- E3's own requirement
    ("query history and audit: what was searched, by whom, and when") is
    satisfied here rather than on every generic GET /events call, which
    would audit-log routine UI polling, not deliberate hunting activity."""
    saved = db.query(SavedQuery).filter(SavedQuery.id == query_id).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved query not found")

    filt = saved.filter or {}
    q = db.query(NormalizedEvent)
    if filt.get("source_id"):
        q = q.filter(NormalizedEvent.source_id == filt["source_id"])
    if filt.get("severity"):
        q = q.filter(NormalizedEvent.severity == filt["severity"].lower())
    if filt.get("risk_level"):
        q = q.filter(NormalizedEvent.risk_level == filt["risk_level"].upper())
    if filt.get("q"):
        term = f"%{filt['q']}%"
        q = q.filter((NormalizedEvent.message.ilike(term)) | (NormalizedEvent.source_ip.ilike(term)) | (NormalizedEvent.dest_ip.ilike(term)))

    total = q.count()
    items = q.order_by(NormalizedEvent.timestamp.desc()).limit(100).all()

    db.add(AuditLog(
        user=current_user.id, action="hunt_query_executed", entity_type="SavedQuery", entity_id=query_id,
        after_state={"name": saved.name, "filter": filt, "result_count": total},
    ))
    db.commit()

    return {"total": total, "events": [e.canonical_json for e in items if e.canonical_json]}


def _out(q: SavedQuery) -> dict:
    return {
        "id": q.id, "name": q.name, "filter": q.filter, "owner": q.owner,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }
