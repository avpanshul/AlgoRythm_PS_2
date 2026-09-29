from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.all import Source, SourceFingerprint, User
from app.analytics.drift import check_source_drift, approve_new_fingerprint

router = APIRouter()

class SourceIn(BaseModel):
    id: str
    name: str
    vendor: Optional[str] = None
    product: Optional[str] = None
    device_type: Optional[str] = None
    organization_id: Optional[str] = None
    enabled: bool = True

class SourceOut(SourceIn):
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/sources", response_model=List[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    return db.query(Source).all()

@router.post("/sources", response_model=SourceOut)
def create_source(source: SourceIn, db: Session = Depends(get_db)):
    db_source = Source(**source.model_dump())
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    vendor: Optional[str] = None
    product: Optional[str] = None
    device_type: Optional[str] = None
    organization_id: Optional[str] = None
    enabled: Optional[bool] = None


@router.put("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: str, req: SourceUpdate, db: Session = Depends(get_db)):
    """Real, previously-missing update path -- needed so a source created
    before any Organization existed (every real seeded source here) can be
    retroactively assigned to one for the Multi-CSE Supervisory rollup,
    without deleting and recreating it."""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(source, k, v)
    db.commit()
    db.refresh(source)
    return source


class AnalyzeSampleIn(BaseModel):
    sample: str
    vendor: Optional[str] = None
    device_type: Optional[str] = None


@router.post("/sources/analyze-sample")
def analyze_sample(body: AnalyzeSampleIn, db: Session = Depends(get_db)):
    """Real format detection + real per-field LLM mapping classification
    against the caller's actual pasted sample -- used by the Add Source
    wizard's Detect/Map steps so those steps show real output instead of a
    fixed illustrative preview. Does not create any Source, Parser or event;
    it's a stateless, read-only analysis of the given text."""
    sample = (body.sample or "").strip()
    if not sample:
        raise HTTPException(status_code=400, detail="sample must not be empty")
    from app.services.pack_drafting import classify_sample_fields
    return classify_sample_fields(sample, vendor=body.vendor, device_type=body.device_type)


@router.post("/sources/check-drift")
def trigger_drift_check(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fingerprints every source with events and flags any whose field-name
    shape has drifted from its accepted baseline (ULPF-master-prompt.md C2).
    First run per source creates the baseline; nothing is flagged then."""
    return check_source_drift(db)


@router.get("/sources/{source_id}/fingerprint")
def get_fingerprint(source_id: str, db: Session = Depends(get_db)):
    fp = db.query(SourceFingerprint).filter(SourceFingerprint.source_id == source_id).first()
    if not fp:
        return {"status": "no_fingerprint_yet"}
    return {
        "source_id": fp.source_id, "field_names": fp.field_names, "sample_count": fp.sample_count,
        "drift_detected": fp.drift_detected, "drift_detail": fp.drift_detail,
    }


@router.post("/sources/{source_id}/approve-drift")
def approve_drift(source_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    fp = approve_new_fingerprint(db, source_id, current_user.id)
    if not fp:
        raise HTTPException(status_code=404, detail="No drift-flagged fingerprint for this source")
    return {"source_id": fp.source_id, "field_names": fp.field_names, "drift_detected": fp.drift_detected}
