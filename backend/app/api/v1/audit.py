"""Audit logs API endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.models.all import AuditLog, verify_audit_chain

router = APIRouter()


@router.get("/audit-logs/verify")
def verify_audit_logs(db: Session = Depends(get_db)):
    """Re-walks the tamper-evident hash chain (see AuditLog's before_insert
    listener in app/models/all.py) and reports the first broken link, if
    any -- the scheduled self-verification job this endpoint backs is what
    makes "tamper-evident" a checked claim rather than an assumed one."""
    return verify_audit_chain(db)

@router.get("/audit-logs")
def list_audit_logs(
    user: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    
    if user:
        query = query.filter(AuditLog.user.ilike(f"%{user}%"))
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        query = query.filter(AuditLog.entity_type.ilike(f"%{entity_type}%"))
    if q:
        query = query.filter(
            (AuditLog.user.ilike(f"%{q}%")) | 
            (AuditLog.action.ilike(f"%{q}%")) |
            (AuditLog.entity_id.ilike(f"%{q}%")) |
            (AuditLog.reason.ilike(f"%{q}%"))
        )
        
    total = query.count()
    items = query.order_by(AuditLog.timestamp.desc()).offset((page - 1) * size).limit(size).all()
    
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": a.id,
                "user": a.user,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "reason": a.reason,
                "ip_address": getattr(a, 'ip_address', 'internal'), # some mock data might not have ip
                "timestamp": a.timestamp.isoformat() if a.timestamp else None
            }
            for a in items
        ]
    }
