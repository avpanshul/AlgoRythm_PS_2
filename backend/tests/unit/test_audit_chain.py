"""Tests for the audit-log hash chain (ULPF-master-prompt.md Part D5:
tamper-evident admin audit log). Uses a real in-memory SQLite DB and the
real ORM insert path (the before_insert listener in app/models/all.py),
not a hand-rolled reimplementation of the hashing -- if the listener breaks,
these tests exercise the exact code path production uses."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.all import AuditLog, verify_audit_chain


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


class TestAuditChain:
    def test_chain_verifies_on_untampered_log(self):
        db = _fresh_db()
        for i in range(5):
            db.add(AuditLog(user=f"user{i}", action="test_action", entity_type="Thing", entity_id=str(i)))
            db.commit()

        result = verify_audit_chain(db)
        assert result["valid"] is True
        assert result["checked"] == 5

    def test_each_row_links_to_the_previous_hash(self):
        db = _fresh_db()
        db.add(AuditLog(user="a", action="act1", entity_type="T", entity_id="1"))
        db.commit()
        db.add(AuditLog(user="b", action="act2", entity_type="T", entity_id="2"))
        db.commit()

        rows = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
        assert rows[0].prev_hash == ""
        assert rows[1].prev_hash == rows[0].hash
        assert rows[0].hash != rows[1].hash

    def test_tampering_with_a_historical_row_is_detected(self):
        db = _fresh_db()
        for i in range(3):
            db.add(AuditLog(user=f"user{i}", action="original_action", entity_type="Thing", entity_id=str(i)))
            db.commit()

        assert verify_audit_chain(db)["valid"] is True

        # Simulate an attacker/DBA editing a historical row directly (bypassing
        # the ORM insert listener, as any raw SQL UPDATE would) -- this is
        # exactly the scenario the hash chain exists to catch.
        row = db.query(AuditLog).filter(AuditLog.id == 2).first()
        row.action = "tampered_action"
        db.commit()

        result = verify_audit_chain(db)
        assert result["valid"] is False
        assert result["broken_at_id"] == 2

    def test_deleting_a_row_breaks_the_chain(self):
        db = _fresh_db()
        for i in range(3):
            db.add(AuditLog(user=f"user{i}", action="act", entity_type="Thing", entity_id=str(i)))
            db.commit()

        row = db.query(AuditLog).filter(AuditLog.id == 2).first()
        db.delete(row)
        db.commit()

        result = verify_audit_chain(db)
        assert result["valid"] is False
