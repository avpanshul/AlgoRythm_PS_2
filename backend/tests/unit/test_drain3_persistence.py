"""Tests for Item 4: Drain3 template-store persistence and the
counter-reseed collision-prevention safety net.

Real drain3.TemplateMiner + real FilePersistence against real temp files --
not mocked, per this project's no-mocking rule.
"""
import sys
import os
import tempfile
import shutil
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import app.ai.drain3_engine as drain3_engine_module
from app.ai.drain3_engine import Drain3Engine
from app.core.config import settings
from app.core.database import Base
from app.models.all import UnknownTemplate
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _fresh_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


class TestPersistenceAcrossRestart:
    def test_cluster_ids_stay_consistent_across_a_simulated_restart(self):
        tmp_dir = tempfile.mkdtemp()
        original_path = drain3_engine_module.PERSIST_PATH
        original_flag = settings.ENABLE_DRAIN_PERSIST
        drain3_engine_module.PERSIST_PATH = os.path.join(tmp_dir, "drain3_state.bin")
        settings.ENABLE_DRAIN_PERSIST = True
        try:
            engine_a = Drain3Engine()
            r1 = engine_a.extract_template("Connection refused from 10.0.0.1")
            r2 = engine_a.extract_template("Connection refused from 10.0.0.2")
            cluster_id_1 = r1["cluster_id"]

            # Simulate a restart: a brand-new Drain3Engine, same persist path.
            engine_b = Drain3Engine()
            r3 = engine_b.extract_template("Connection refused from 10.0.0.3")

            # Same template family -> same cluster ID as before the "restart",
            # not a fresh counter starting at 1 again.
            assert r3["cluster_id"] == cluster_id_1
        finally:
            settings.ENABLE_DRAIN_PERSIST = original_flag
            drain3_engine_module.PERSIST_PATH = original_path
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_corrupt_state_file_falls_back_to_empty_start(self):
        tmp_dir = tempfile.mkdtemp()
        original_path = drain3_engine_module.PERSIST_PATH
        original_flag = settings.ENABLE_DRAIN_PERSIST
        bad_path = os.path.join(tmp_dir, "drain3_state.bin")
        with open(bad_path, "wb") as f:
            f.write(b"not a real drain3 snapshot")
        drain3_engine_module.PERSIST_PATH = bad_path
        settings.ENABLE_DRAIN_PERSIST = True
        try:
            # Must not raise -- falls back to empty-start per the requirement.
            engine = Drain3Engine()
            result = engine.extract_template("some log line")
            assert result["cluster_id"] >= 1
            assert os.path.exists(bad_path + ".corrupt")
        finally:
            settings.ENABLE_DRAIN_PERSIST = original_flag
            drain3_engine_module.PERSIST_PATH = original_path
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestCounterReseedSafetyNet:
    def test_fresh_engine_seeds_counter_above_existing_db_rows(self):
        """Even with persistence OFF (today's default), a fresh miner must
        not hand out a cluster_id that collides with a real existing
        UnknownTemplate row -- this is the exact bug the live audit found."""
        original_flag = settings.ENABLE_DRAIN_PERSIST
        settings.ENABLE_DRAIN_PERSIST = False
        try:
            db = _fresh_db()
            db.add(UnknownTemplate(cluster_id="7", template_str="old real template", event_count=50))
            db.commit()

            engine = Drain3Engine()

            import app.core.database as database
            original_session_local = database.SessionLocal
            database.SessionLocal = sessionmaker(bind=db.get_bind())
            try:
                result = engine.extract_template(f"a genuinely new never-seen line {uuid.uuid4().hex}")
            finally:
                database.SessionLocal = original_session_local

            # New cluster's id must be > 7, never colliding with the real
            # pre-existing row.
            assert result["cluster_id"] > 7
        finally:
            settings.ENABLE_DRAIN_PERSIST = original_flag

    def test_seeding_only_happens_once(self):
        original_flag = settings.ENABLE_DRAIN_PERSIST
        settings.ENABLE_DRAIN_PERSIST = False
        try:
            engine = Drain3Engine()
            assert engine._counter_seeded is False
            engine.extract_template("first line")
            assert engine._counter_seeded is True
            counter_after_first = engine.miner.drain.clusters_counter
            engine.extract_template("second, different line")
            # seeding logic doesn't run again and clobber the counter back down
            assert engine.miner.drain.clusters_counter >= counter_after_first
        finally:
            settings.ENABLE_DRAIN_PERSIST = original_flag
