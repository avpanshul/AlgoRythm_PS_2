"""Entity behavioral profile API (ULPF-phase2-prompt.md E7a "Sentinel") --
read the per-entity profiles app/ai/sentinel.py builds from real event
history, and trigger a batch update on demand."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.all import EntityProfile, User
from app.ai.sentinel import update_all_profiles

router = APIRouter()


@router.post("/entities/update-profiles")
def trigger_profile_update(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return update_all_profiles(db)


@router.get("/entities")
def list_entities(
    min_risk_score: float = Query(0, ge=0),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(EntityProfile).filter(EntityProfile.risk_score >= min_risk_score)
    total = q.count()
    items = q.order_by(EntityProfile.risk_score.desc()).offset((page - 1) * size).limit(size).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "entity_id": p.entity_id,
                "entity_type": p.entity_type,
                "risk_score": p.risk_score,
                "event_count": p.event_count,
                "known_dest_port_count": len(p.known_dest_ports or []),
                "known_peer_count": len(p.known_peers or []),
                "last_event_at": p.last_event_at.isoformat() if p.last_event_at else None,
            }
            for p in items
        ],
    }


@router.get("/entities/{entity_id}/profile")
def get_entity_profile(entity_id: str, db: Session = Depends(get_db)):
    profile = db.query(EntityProfile).filter(EntityProfile.entity_id == entity_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile for this entity yet")
    return {
        "entity_id": profile.entity_id,
        "entity_type": profile.entity_type,
        "risk_score": profile.risk_score,
        "event_count": profile.event_count,
        "known_dest_ports": profile.known_dest_ports,
        "known_protocols": profile.known_protocols,
        "known_peers": profile.known_peers,
        "reason_log": profile.reason_log,
        "last_event_at": profile.last_event_at.isoformat() if profile.last_event_at else None,
    }
