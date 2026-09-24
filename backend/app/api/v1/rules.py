"""Correlation Rules CRUD."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.all import CorrelationRule, AuditLog

router = APIRouter()

class RuleCreate(BaseModel):
    name: str
    description: str
    severity: str
    enabled: bool = True
    condition: dict
    threshold: int
    time_window_seconds: int

class RuleUpdate(BaseModel):
    name: str = None
    description: str = None
    severity: str = None
    enabled: bool = None
    condition: dict = None
    threshold: int = None
    time_window_seconds: int = None


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    rules = db.query(CorrelationRule).order_by(CorrelationRule.created_at.desc()).all()
    return rules


@router.post("/rules")
def create_rule(req: RuleCreate, db: Session = Depends(get_db)):
    rule = CorrelationRule(
        name=req.name,
        description=req.description,
        severity=req.severity,
        enabled=req.enabled,
        condition=req.condition,
        threshold=req.threshold,
        time_window_seconds=req.time_window_seconds,
        created_by="admin"
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    audit = AuditLog(user="admin", action="rule_created", entity_type="CorrelationRule", entity_id=str(rule.id))
    db.add(audit)
    db.commit()
    
    return rule


@router.get("/rules/{rule_id}")
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(CorrelationRule).filter(CorrelationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, req: RuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(CorrelationRule).filter(CorrelationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
        
    rule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule)
    
    audit = AuditLog(user="admin", action="rule_updated", entity_type="CorrelationRule", entity_id=str(rule.id))
    db.add(audit)
    db.commit()
    
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(CorrelationRule).filter(CorrelationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    db.delete(rule)
    
    audit = AuditLog(user="admin", action="rule_deleted", entity_type="CorrelationRule", entity_id=str(rule.id))
    db.add(audit)
    db.commit()
    
    return {"status": "deleted", "rule_id": rule_id}
