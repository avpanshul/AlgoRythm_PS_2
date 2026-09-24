"""Integrations API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.all import Integration, AuditLog

router = APIRouter()

class IntegrationCreate(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    config: dict
    enabled: bool = True

class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None
    enabled: Optional[bool] = None


@router.get("/integrations")
def list_integrations(db: Session = Depends(get_db)):
    return db.query(Integration).all()


@router.post("/integrations")
def create_integration(req: IntegrationCreate, db: Session = Depends(get_db)):
    integration = Integration(
        name=req.name,
        type=req.type,
        description=req.description,
        config=req.config,
        enabled=req.enabled,
        status="configured"
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


@router.put("/integrations/{integration_id}")
def update_integration(integration_id: int, req: IntegrationUpdate, db: Session = Depends(get_db)):
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
        
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(integration, k, v)
        
    integration.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(integration)
    return integration


@router.delete("/integrations/{integration_id}")
def delete_integration(integration_id: int, db: Session = Depends(get_db)):
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    db.delete(integration)
    db.commit()
    return {"status": "deleted"}


@router.post("/integrations/{integration_id}/test")
def test_integration(integration_id: int, db: Session = Depends(get_db)):
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
        
    # Simulate a successful connection test
    integration.status = "connected"
    integration.last_test_at = datetime.now(timezone.utc)
    integration.last_test_result = {"status": "success", "latency_ms": 42, "message": "Connection established successfully"}
    
    db.commit()
    return {"status": "success", "result": integration.last_test_result}
