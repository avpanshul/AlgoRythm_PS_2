from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.all import MappingRegistry, AuditLog, User
from app.schemas.canonical import CanonicalEvent
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

router = APIRouter()

class MappingOut(BaseModel):
    id: int
    vendor: str
    device_type: Optional[str]
    raw_field: str
    canonical_field: str
    mapping_type: str
    confidence: float
    approved: bool
    approved_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ApproveRequest(BaseModel):
    reviewer: str
    canonical_field: Optional[str] = None  # Allow override

class RejectRequest(BaseModel):
    reviewer: str
    reason: Optional[str] = None

@router.get("/mappings", response_model=List[MappingOut])
def list_mappings(
    approved: Optional[bool] = None,
    needs_review: bool = False,
    db: Session = Depends(get_db)
):
    q = db.query(MappingRegistry)
    if needs_review:
        q = q.filter(MappingRegistry.approved == False)
    elif approved is not None:
        q = q.filter(MappingRegistry.approved == approved)
    return q.order_by(MappingRegistry.created_at.desc()).all()

@router.post("/mappings/{mapping_id}/approve")
def approve_mapping(mapping_id: int, req: ApproveRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    mapping = db.query(MappingRegistry).filter(MappingRegistry.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    if current_user.role_name not in ("admin", "approver", "parser_author"):
        raise HTTPException(status_code=403, detail="Insufficient role to approve a mapping")

    before = {"canonical_field": mapping.canonical_field, "approved": mapping.approved}

    if req.canonical_field:
        mapping.canonical_field = req.canonical_field
    mapping.approved = True
    # The reviewer identity is the authenticated actor, never the client-supplied
    # `req.reviewer` string -- that field was previously trusted as-is, letting
    # any authenticated caller attribute an approval to an arbitrary name.
    mapping.approved_by = current_user.id
    mapping.updated_at = datetime.now(timezone.utc)

    # Audit
    audit = AuditLog(
        user=current_user.id,
        action="mapping_approved",
        entity_type="MappingRegistry",
        entity_id=str(mapping_id),
        before_state=before,
        after_state={"canonical_field": mapping.canonical_field, "approved": True}
    )
    db.add(audit)
    db.commit()
    return {"status": "approved", "mapping_id": mapping_id}

@router.post("/mappings/{mapping_id}/reject")
def reject_mapping(mapping_id: int, req: RejectRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    mapping = db.query(MappingRegistry).filter(MappingRegistry.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    if current_user.role_name not in ("admin", "approver", "parser_author"):
        raise HTTPException(status_code=403, detail="Insufficient role to reject a mapping")

    before = {"canonical_field": mapping.canonical_field, "approved": mapping.approved}
    db.delete(mapping)

    # Audit
    audit = AuditLog(
        user=current_user.id,
        action="mapping_rejected",
        entity_type="MappingRegistry",
        entity_id=str(mapping_id),
        before_state=before,
        after_state=None,
        reason=req.reason
    )
    db.add(audit)
    db.commit()
    return {"status": "rejected", "mapping_id": mapping_id}
