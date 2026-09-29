"""Incident case management API (ULPF-phase2-prompt.md E6)."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.all import Case, Notification, OnCallContact, CorrelatedIncident, User
from app.notifications.engine import notify, acknowledge, check_escalations

router = APIRouter()


class CaseCreate(BaseModel):
    title: str
    severity: str = "medium"
    correlation_id: Optional[str] = None
    owner: Optional[str] = None


class CaseUpdate(BaseModel):
    status: Optional[str] = None
    owner: Optional[str] = None
    severity: Optional[str] = None
    note: Optional[str] = None


class ContactCreate(BaseModel):
    name: str
    channel: str  # "sms" or "console"
    address: str
    escalation_order: int = 0


class AckRequest(BaseModel):
    acknowledged_by: str


@router.post("/cases")
def create_case(req: CaseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if req.severity not in ("low", "medium", "high", "critical"):
        raise HTTPException(status_code=400, detail="severity must be one of: low, medium, high, critical")
    if req.correlation_id and not db.query(CorrelatedIncident).filter(CorrelatedIncident.id == req.correlation_id).first():
        raise HTTPException(status_code=404, detail="correlation_id does not reference an existing correlated incident")

    case = Case(
        id=f"case-{uuid.uuid4().hex[:16]}", title=req.title, severity=req.severity,
        correlation_id=req.correlation_id, owner=req.owner,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return _case_out(case)


@router.get("/cases")
def list_cases(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Case)
    if status:
        q = q.filter(Case.status == status)
    if severity:
        q = q.filter(Case.severity == severity)
    total = q.count()
    items = q.order_by(Case.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {"total": total, "page": page, "size": size, "items": [_case_out(c) for c in items]}


@router.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    notifications = db.query(Notification).filter(Notification.case_id == case_id).order_by(Notification.created_at.asc()).all()
    out = _case_out(case)
    out["notifications"] = [_notification_out(n) for n in notifications]
    return out


@router.patch("/cases/{case_id}")
def update_case(case_id: str, req: CaseUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if req.status:
        if req.status not in ("open", "investigating", "resolved", "false_positive"):
            raise HTTPException(status_code=400, detail="invalid status")
        case.status = req.status
        if req.status in ("resolved", "false_positive"):
            case.resolved_at = datetime.now(timezone.utc)
    if req.owner is not None:
        case.owner = req.owner
    if req.severity:
        if req.severity not in ("low", "medium", "high", "critical"):
            raise HTTPException(status_code=400, detail="invalid severity")
        case.severity = req.severity
    if req.note:
        case.notes = (case.notes or []) + [{
            "timestamp": datetime.now(timezone.utc).isoformat(), "user": current_user.id, "note": req.note,
        }]
    db.commit()
    db.refresh(case)
    return _case_out(case)


@router.post("/cases/{case_id}/notify")
def notify_case(case_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    notification = notify(db, case)
    return _notification_out(notification)


@router.post("/notifications/{notification_id}/ack")
def ack_notification(notification_id: str, req: AckRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    notification = acknowledge(db, notification_id, req.acknowledged_by or current_user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return _notification_out(notification)


@router.post("/notifications/check-escalations")
def trigger_escalation_check(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    escalated = check_escalations(db)
    return {"escalated_count": len(escalated), "notifications": [_notification_out(n) for n in escalated]}


@router.get("/oncall")
def list_contacts(db: Session = Depends(get_db)):
    contacts = db.query(OnCallContact).order_by(OnCallContact.escalation_order.asc()).all()
    return [_contact_out(c) for c in contacts]


@router.post("/oncall")
def create_contact(req: ContactCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if req.channel not in ("sms", "console"):
        raise HTTPException(status_code=400, detail="channel must be 'sms' or 'console'")
    contact = OnCallContact(
        id=f"contact-{uuid.uuid4().hex[:16]}", name=req.name, channel=req.channel,
        address=req.address, escalation_order=req.escalation_order,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return _contact_out(contact)


def _case_out(c: Case) -> dict:
    return {
        "id": c.id, "correlation_id": c.correlation_id, "title": c.title,
        "severity": c.severity, "status": c.status, "owner": c.owner, "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
        "time_to_resolve_seconds": (c.resolved_at - c.created_at).total_seconds() if c.resolved_at and c.created_at else None,
    }


def _notification_out(n: Notification) -> dict:
    time_to_ack = None
    if n.sent_at and n.acknowledged_at:
        time_to_ack = (n.acknowledged_at - n.sent_at).total_seconds()
    return {
        "id": n.id, "case_id": n.case_id, "contact_id": n.contact_id, "channel": n.channel,
        "status": n.status, "detail": n.detail,
        "sent_at": n.sent_at.isoformat() if n.sent_at else None,
        "acknowledged_at": n.acknowledged_at.isoformat() if n.acknowledged_at else None,
        "acknowledged_by": n.acknowledged_by,
        "escalated_at": n.escalated_at.isoformat() if n.escalated_at else None,
        "time_to_ack_seconds": time_to_ack,
    }


def _contact_out(c: OnCallContact) -> dict:
    return {
        "id": c.id, "name": c.name, "channel": c.channel, "address": c.address,
        "escalation_order": c.escalation_order, "enabled": c.enabled,
    }
