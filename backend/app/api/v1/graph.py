"""Entity graph + attack path API (ULPF-phase2-prompt.md E2/E8)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.analytics.graph import build_graph, reconstruct_attack_path, build_timeline

router = APIRouter()


@router.get("/graph")
def get_graph(entity: Optional[str] = None, limit: int = Query(2000, ge=1, le=2000), db: Session = Depends(get_db)):
    return build_graph(db, entity=entity, limit=limit)


@router.get("/attack-path")
def get_attack_path(entity: str, max_hops: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    return reconstruct_attack_path(db, entity=entity, max_hops=max_hops)


@router.get("/timeline")
def get_timeline(
    entity: Optional[str] = None,
    incident_id: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return build_timeline(db, entity=entity, incident_id=incident_id, limit=limit)
