"""Privacy policy CRUD. The PrivacyPolicy table existed with no API at all
until now -- the frontend page for this was pure mock data with nothing real
to wire to."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.all import PrivacyPolicy, AuditLog

router = APIRouter()


class PrivacyPolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rules: list = []
    enabled: bool = True
    scope: str = "all"


class PrivacyPolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[list] = None
    enabled: Optional[bool] = None
    scope: Optional[str] = None


@router.get("/privacy-policies")
def list_privacy_policies(db: Session = Depends(get_db)):
    return db.query(PrivacyPolicy).order_by(PrivacyPolicy.created_at.desc()).all()


@router.post("/privacy-policies")
def create_privacy_policy(req: PrivacyPolicyCreate, db: Session = Depends(get_db)):
    policy = PrivacyPolicy(
        name=req.name, description=req.description, rules=req.rules,
        enabled=req.enabled, scope=req.scope, created_by="admin",
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)

    db.add(AuditLog(user="admin", action="privacy_policy_created", entity_type="PrivacyPolicy", entity_id=str(policy.id)))
    db.commit()
    return policy


@router.put("/privacy-policies/{policy_id}")
def update_privacy_policy(policy_id: int, req: PrivacyPolicyUpdate, db: Session = Depends(get_db)):
    policy = db.query(PrivacyPolicy).filter(PrivacyPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Privacy policy not found")

    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(policy, k, v)
    policy.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(policy)

    db.add(AuditLog(user="admin", action="privacy_policy_updated", entity_type="PrivacyPolicy", entity_id=str(policy.id)))
    db.commit()
    return policy


@router.delete("/privacy-policies/{policy_id}")
def delete_privacy_policy(policy_id: int, db: Session = Depends(get_db)):
    policy = db.query(PrivacyPolicy).filter(PrivacyPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Privacy policy not found")
    db.delete(policy)
    db.add(AuditLog(user="admin", action="privacy_policy_deleted", entity_type="PrivacyPolicy", entity_id=str(policy_id)))
    db.commit()
    return {"status": "deleted", "policy_id": policy_id}
