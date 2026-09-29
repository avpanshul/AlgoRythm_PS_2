r"""Severity-tiered notification dispatch, dedup, rate limiting, and
escalation (ULPF-phase2-prompt.md E6).

Severity tiers, per the spec's own wording:
  low      -> dashboard-only (no notification)
  medium   -> analyst queue (no external notification -- visible in-app via
              GET /cases, same as any other open case)
  high     -> immediate notification to the current on-call contact
  critical -> immediate notification, escalated to the next on-call contact
              if unacknowledged within settings.ESCALATION_TIMEOUT_MINUTES

Dedup: a still-open case that gets notify() called on it repeatedly (e.g.
because a correlation re-evaluation keeps touching it) does not re-notify
every time -- only after NOTIFICATION_DEDUP_MINUTES since the last one for
the same case+severity.

Rate limit: a contact cannot receive more than
NOTIFICATION_RATE_LIMIT_PER_HOUR notifications in a rolling hour, regardless
of how many different cases fire -- a burst of correlated incidents
shouldn't be able to flood one person's phone.

Every send/ack/escalate is written to the existing tamper-evident AuditLog
(app/models/all.py's hash-chained table), not a separate log.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.all import Case, Notification, OnCallContact, AuditLog
from app.notifications.channels import get_channel

_SEVERITY_ACTION = {
    "low": "dashboard_only",
    "medium": "analyst_queue",
    "high": "notify",
    "critical": "notify_and_escalate",
}


def _next_contact(db: Session, exclude_ids: set) -> OnCallContact:
    return (
        db.query(OnCallContact)
        .filter(OnCallContact.enabled.is_(True), ~OnCallContact.id.in_(exclude_ids) if exclude_ids else True)
        .order_by(OnCallContact.escalation_order.asc())
        .first()
    )


def notify(db: Session, case: Case) -> Notification:
    """Runs the severity-tier decision for `case` and, if the tier calls for
    an external notification, sends it (dedup/rate-limit permitting) and
    records a Notification row either way -- even a "dashboard_only" or
    "deduped" outcome is worth a row, so the case's notification history is
    complete, not just its successes."""
    from app.core.config import settings
    import uuid

    action = _SEVERITY_ACTION.get(case.severity, "analyst_queue")

    if action in ("dashboard_only", "analyst_queue"):
        notif = Notification(
            id=f"notif-{uuid.uuid4().hex[:16]}", case_id=case.id, channel="none",
            dedup_key=f"{case.id}:{case.severity}", status=action,
            detail=f"severity={case.severity} does not trigger an external notification",
        )
        db.add(notif)
        db.commit()
        return notif

    dedup_key = f"{case.id}:{case.severity}"
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.NOTIFICATION_DEDUP_MINUTES)
    recent = (
        db.query(Notification)
        .filter(Notification.dedup_key == dedup_key, Notification.created_at >= cutoff, Notification.status == "sent")
        .first()
    )
    if recent:
        notif = Notification(
            id=f"notif-{uuid.uuid4().hex[:16]}", case_id=case.id, channel="none",
            dedup_key=dedup_key, status="deduped",
            detail=f"a notification for this case+severity was already sent at {recent.sent_at} "
                   f"(within the {settings.NOTIFICATION_DEDUP_MINUTES}-minute dedup window)",
        )
        db.add(notif)
        db.commit()
        return notif

    contact = _next_contact(db, exclude_ids=set())
    if not contact:
        notif = Notification(
            id=f"notif-{uuid.uuid4().hex[:16]}", case_id=case.id, channel="none",
            dedup_key=dedup_key, status="failed",
            detail="no enabled on-call contact is registered -- add one via POST /oncall",
        )
        db.add(notif)
        db.commit()
        _audit(db, "notification_failed_no_contact", case.id, {"reason": notif.detail})
        return notif

    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_to_contact = (
        db.query(Notification)
        .filter(Notification.contact_id == contact.id, Notification.created_at >= hour_ago, Notification.status == "sent")
        .count()
    )
    if recent_to_contact >= settings.NOTIFICATION_RATE_LIMIT_PER_HOUR:
        notif = Notification(
            id=f"notif-{uuid.uuid4().hex[:16]}", case_id=case.id, contact_id=contact.id, channel=contact.channel,
            dedup_key=dedup_key, status="rate_limited",
            detail=f"{contact.name} has already received {recent_to_contact} notifications in the last hour "
                   f"(limit {settings.NOTIFICATION_RATE_LIMIT_PER_HOUR})",
        )
        db.add(notif)
        db.commit()
        _audit(db, "notification_rate_limited", case.id, {"contact": contact.id})
        return notif

    channel = get_channel(contact.channel)
    message = f"[{case.severity.upper()}] {case.title} (case {case.id})"
    result = channel.send(contact.address, message)

    now = datetime.now(timezone.utc)
    notif = Notification(
        id=f"notif-{uuid.uuid4().hex[:16]}", case_id=case.id, contact_id=contact.id, channel=contact.channel,
        dedup_key=dedup_key, status=result.status, detail=result.detail,
        sent_at=now if result.status == "sent" else None,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    _audit(db, f"notification_{result.status}", case.id, {"contact": contact.id, "channel": contact.channel, "detail": result.detail})
    return notif


def acknowledge(db: Session, notification_id: str, acknowledged_by: str) -> Notification:
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        return None
    notif.acknowledged_at = datetime.now(timezone.utc)
    notif.acknowledged_by = acknowledged_by
    notif.status = "acknowledged"
    db.commit()
    db.refresh(notif)
    time_to_ack = None
    if notif.sent_at:
        time_to_ack = (notif.acknowledged_at - notif.sent_at).total_seconds()
    _audit(db, "notification_acknowledged", notif.case_id, {
        "notification_id": notif.id, "acknowledged_by": acknowledged_by,
        "time_to_ack_seconds": time_to_ack,
    })
    return notif


def check_escalations(db: Session) -> list:
    """Finds critical-severity notifications sent but not acknowledged
    within the escalation timeout, and notifies the next on-call contact in
    line. Callable on demand or from a scheduler -- same on-demand-batch
    pattern as app/analytics/correlation.py and app/ai/sentinel.py."""
    from app.core.config import settings

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.ESCALATION_TIMEOUT_MINUTES)
    overdue = (
        db.query(Notification)
        .filter(
            Notification.status == "sent",
            Notification.acknowledged_at.is_(None),
            Notification.escalated_at.is_(None),
            Notification.sent_at.isnot(None),
            Notification.sent_at <= cutoff,
        )
        .all()
    )

    escalated = []
    for notif in overdue:
        case = db.query(Case).filter(Case.id == notif.case_id).first()
        if not case or case.severity != "critical":
            continue  # escalation is a critical-severity behavior, per the spec

        next_contact = _next_contact(db, exclude_ids={notif.contact_id} if notif.contact_id else set())
        if not next_contact:
            continue

        channel = get_channel(next_contact.channel)
        message = f"[ESCALATED] [{case.severity.upper()}] {case.title} (case {case.id}) -- unacknowledged for {settings.ESCALATION_TIMEOUT_MINUTES}+ min"
        result = channel.send(next_contact.address, message)

        import uuid
        now = datetime.now(timezone.utc)
        new_notif = Notification(
            id=f"notif-{uuid.uuid4().hex[:16]}", case_id=case.id, contact_id=next_contact.id,
            channel=next_contact.channel, dedup_key=f"{case.id}:escalation",
            status=result.status, detail=result.detail, sent_at=now if result.status == "sent" else None,
        )
        db.add(new_notif)
        notif.escalated_at = now
        db.commit()
        _audit(db, "notification_escalated", case.id, {
            "from_notification": notif.id, "to_contact": next_contact.id, "new_notification": new_notif.id,
        })
        escalated.append(new_notif)

    return escalated


def _audit(db: Session, action: str, case_id: str, detail: dict):
    db.add(AuditLog(user="system", action=action, entity_type="Case", entity_id=case_id, after_state=detail))
    db.commit()
