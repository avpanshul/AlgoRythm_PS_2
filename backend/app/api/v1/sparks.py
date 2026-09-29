"""Item 2: spark detection API. Real rows only -- if ENABLE_SPARK_DETECTION
was never turned on, this honestly returns an empty list, never a fabricated
example spark."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.all import Spark
from app.analytics.graph import build_timeline

router = APIRouter()


def _spark_dict(s: Spark) -> dict:
    return {
        "id": s.id,
        "entity": s.entity,
        "trigger_type": s.trigger_type,
        "reason": s.reason,
        "source_incident_id": s.source_incident_id,
        "risk_score": s.risk_score,
        "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        "path": s.path or [],
        "hop_count": s.hop_count,
        "front": s.front,
        "proximity_watchlist": s.proximity_watchlist or [],
    }


@router.get("/sparks")
def list_sparks(db: Session = Depends(get_db)):
    rows = db.query(Spark).order_by(Spark.detected_at.desc()).limit(200).all()
    return [_spark_dict(s) for s in rows]


@router.get("/sparks/{spark_id}")
def get_spark(spark_id: str, db: Session = Depends(get_db)):
    spark = db.query(Spark).filter(Spark.id == spark_id).first()
    if not spark:
        raise HTTPException(status_code=404, detail="Spark not found")
    result = _spark_dict(spark)
    result["timeline"] = build_timeline(db, entity=spark.entity)
    return result
