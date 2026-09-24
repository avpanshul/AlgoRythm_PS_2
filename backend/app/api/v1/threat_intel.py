"""Threat Intelligence API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.all import ThreatIndicator

router = APIRouter()

class IndicatorCreate(BaseModel):
    type: str
    value: str
    threat_type: Optional[str] = None
    severity: str = "medium"
    source: Optional[str] = "manual"
    description: Optional[str] = None

class ThreatCheckRequest(BaseModel):
    indicators: List[str]


@router.get("/threat-intel/indicators")
def list_indicators(db: Session = Depends(get_db)):
    return db.query(ThreatIndicator).all()


@router.post("/threat-intel/indicators")
def create_indicator(req: IndicatorCreate, db: Session = Depends(get_db)):
    if db.query(ThreatIndicator).filter(ThreatIndicator.value == req.value).first():
        raise HTTPException(status_code=400, detail="Indicator already exists")
        
    indicator = ThreatIndicator(**req.model_dump())
    db.add(indicator)
    db.commit()
    db.refresh(indicator)
    return indicator


@router.post("/threat-intel/check")
def check_threat(req: ThreatCheckRequest, db: Session = Depends(get_db)):
    # Find matching indicators
    matches = db.query(ThreatIndicator).filter(
        ThreatIndicator.value.in_(req.indicators),
        ThreatIndicator.active == True
    ).all()
    
    # Increment hit counts
    now = datetime.now(timezone.utc)
    for match in matches:
        match.hits += 1
        match.last_seen = now
    
    if matches:
        db.commit()
        
    return {
        "matched": len(matches) > 0,
        "matches": [
            {
                "type": m.type,
                "value": m.value,
                "threat_type": m.threat_type,
                "severity": m.severity,
                "source": m.source
            } for m in matches
        ]
    }
