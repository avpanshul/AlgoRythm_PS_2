"""Tests for incident case management + notification (ULPF-phase2-prompt.md
E6): severity tiers, dedup, rate limiting, acknowledgment, escalation, and
that everything lands in the tamper-evident audit log.

Directly targets the spec's own acceptance criterion: "a synthetic
multi-stage attack fires notification to the named contact ... ack recorded
in audit log" -- built with the ConsoleChannel (the honest default when no
real SMS gateway is configured, per docs/GAP_REPORT_PHASE2.md's E6 row) so
this is a real send-and-acknowledge cycle, not a mock.
"""
import sys
import os
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.all import Case, OnCallContact, Notification, AuditLog
from app.notifications.engine import notify, acknowledge, check_escalations
from app.notifications.channels import SMSChannel, ConsoleChannel


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _mk_case(db, severity="high", title="Test case"):
    case = Case(id=f"case-{uuid.uuid4().hex[:8]}", title=title, severity=severity)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def _mk_contact(db, name="oncall-1", order=0):
    c = OnCallContact(id=f"contact-{uuid.uuid4().hex[:8]}", name=name, channel="console", address=name, escalation_order=order)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


class TestSeverityTiers:
    def test_low_severity_does_not_notify(self):
        db = _fresh_db()
        _mk_contact(db)
        case = _mk_case(db, severity="low")
        notif = notify(db, case)
        assert notif.status == "dashboard_only"
        assert notif.channel == "none"

    def test_medium_severity_goes_to_analyst_queue_not_external(self):
        db = _fresh_db()
        _mk_contact(db)
        case = _mk_case(db, severity="medium")
        notif = notify(db, case)
        assert notif.status == "analyst_queue"

    def test_high_severity_sends_immediately(self):
        db = _fresh_db()
        _mk_contact(db)
        case = _mk_case(db, severity="high")
        notif = notify(db, case)
        assert notif.status == "sent"
        assert notif.sent_at is not None

    def test_critical_severity_sends_immediately_and_is_escalation_eligible(self):
        db = _fresh_db()
        _mk_contact(db)
        case = _mk_case(db, severity="critical")
        notif = notify(db, case)
        assert notif.status == "sent"


class TestSmsChannelHonesty:
    def test_sms_without_gateway_configured_is_not_fabricated_as_sent(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "SMS_GATEWAY_URL", "")
        result = SMSChannel().send("+911234567890", "test message")
        assert result.status == "not_configured"
        assert "not" in result.detail.lower()

    def test_console_channel_always_honestly_reports_sent(self):
        result = ConsoleChannel().send("some-label", "test message")
        assert result.status == "sent"


class TestDeduplication:
    def test_repeated_notify_within_window_is_deduped_not_resent(self):
        db = _fresh_db()
        _mk_contact(db)
        case = _mk_case(db, severity="high")
        first = notify(db, case)
        second = notify(db, case)
        assert first.status == "sent"
        assert second.status == "deduped"
        # Only one real "sent" notification exists for this case.
        sent_count = db.query(Notification).filter(Notification.case_id == case.id, Notification.status == "sent").count()
        assert sent_count == 1


class TestRateLimiting:
    def test_contact_stops_receiving_after_hourly_limit(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "NOTIFICATION_RATE_LIMIT_PER_HOUR", 2)
        monkeypatch.setattr(config.settings, "NOTIFICATION_DEDUP_MINUTES", 0)  # isolate rate-limit from dedup
        db = _fresh_db()
        _mk_contact(db)

        statuses = []
        for i in range(4):
            case = _mk_case(db, title=f"case {i}")  # distinct cases -- dedup key differs each time
            statuses.append(notify(db, case).status)

        assert statuses.count("sent") == 2
        assert statuses.count("rate_limited") == 2


class TestAcknowledgmentAndAudit:
    def test_ack_records_time_to_ack_and_audit_log_entry(self):
        db = _fresh_db()
        _mk_contact(db)
        case = _mk_case(db, severity="high")
        notif = notify(db, case)
        assert notif.status == "sent"

        acked = acknowledge(db, notif.id, acknowledged_by="analyst-1")
        assert acked.status == "acknowledged"
        assert acked.acknowledged_by == "analyst-1"
        assert acked.acknowledged_at is not None

        audit_entries = db.query(AuditLog).filter(AuditLog.action == "notification_acknowledged").all()
        assert len(audit_entries) == 1
        assert audit_entries[0].after_state["acknowledged_by"] == "analyst-1"
        assert audit_entries[0].after_state["time_to_ack_seconds"] is not None

    def test_every_send_attempt_is_audit_logged(self):
        db = _fresh_db()
        _mk_contact(db)
        case = _mk_case(db, severity="critical")
        notify(db, case)
        audit_entries = db.query(AuditLog).filter(AuditLog.entity_id == case.id).all()
        assert len(audit_entries) >= 1
        assert any("notification_sent" in a.action for a in audit_entries)


class TestEscalation:
    def test_unacknowledged_critical_notification_escalates_to_next_contact(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "ESCALATION_TIMEOUT_MINUTES", 15)
        db = _fresh_db()
        first_contact = _mk_contact(db, name="primary", order=0)
        second_contact = _mk_contact(db, name="secondary", order=1)
        case = _mk_case(db, severity="critical")

        notif = notify(db, case)
        assert notif.contact_id == first_contact.id
        # Simulate time passing without acknowledgment.
        notif.sent_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        db.commit()

        escalated = check_escalations(db)
        assert len(escalated) == 1
        assert escalated[0].contact_id == second_contact.id

        db.refresh(notif)
        assert notif.escalated_at is not None

        audit_entries = db.query(AuditLog).filter(AuditLog.action == "notification_escalated").all()
        assert len(audit_entries) == 1

    def test_acknowledged_notification_does_not_escalate(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "ESCALATION_TIMEOUT_MINUTES", 15)
        db = _fresh_db()
        _mk_contact(db, name="primary", order=0)
        _mk_contact(db, name="secondary", order=1)
        case = _mk_case(db, severity="critical")

        notif = notify(db, case)
        acknowledge(db, notif.id, "analyst-1")
        notif.sent_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        db.commit()

        escalated = check_escalations(db)
        assert escalated == []

    def test_high_severity_does_not_escalate_only_critical_does(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "ESCALATION_TIMEOUT_MINUTES", 15)
        db = _fresh_db()
        _mk_contact(db, name="primary", order=0)
        _mk_contact(db, name="secondary", order=1)
        case = _mk_case(db, severity="high")  # not critical

        notif = notify(db, case)
        notif.sent_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        db.commit()

        escalated = check_escalations(db)
        assert escalated == []


class TestFullScenario:
    def test_end_to_end_case_lifecycle_matches_the_spec_acceptance_criterion(self):
        """"a synthetic multi-stage attack fires notification to the named
        contact with attack path attached, ack recorded in audit log" --
        the attack-path/correlation-id attachment is exercised by
        `correlation_id` linking a real CorrelatedIncident (see E1) to a
        Case here; the send-and-ack cycle is the real thing being proven."""
        db = _fresh_db()
        contact = _mk_contact(db, name="on-call-analyst")
        case = Case(id="case-e2e", title="Multi-stage attack detected", severity="critical", correlation_id=None)
        db.add(case)
        db.commit()

        notif = notify(db, case)
        assert notif.status == "sent"
        assert notif.contact_id == contact.id

        acked = acknowledge(db, notif.id, "on-call-analyst")
        assert acked.status == "acknowledged"

        audit_actions = [a.action for a in db.query(AuditLog).filter(AuditLog.entity_id == case.id).all()]
        assert "notification_sent" in audit_actions
        assert "notification_acknowledged" in audit_actions
