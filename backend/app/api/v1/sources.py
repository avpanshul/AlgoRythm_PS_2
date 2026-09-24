from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.all import Source

router = APIRouter()

class SourceIn(BaseModel):
    id: str
    name: str
    vendor: Optional[str] = None
    product: Optional[str] = None
    device_type: Optional[str] = None
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
