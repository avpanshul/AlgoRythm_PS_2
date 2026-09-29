"""Tests for the pluggable ingestion backend (ULPF-phase2-prompt.md E5).

The property that matters isn't "confluent_kafka happens to be absent from
this environment" (it was, until it was deliberately installed to live-test
the Kafka path end-to-end against a real broker -- see docs/PKI.md's sibling
writeup in docs/GAP_REPORT_PHASE2.md's E5 row for that verification) -- it's
that the *default sync path never needs it*, checked structurally (no
top-level import of app.core.messaging in ingestion.py) rather than by
relying on the environment's package list, which can change for good reason.
"""
import ast
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import app.api.v1.ingestion as ingestion_module


class TestSyncBackendDoesNotTouchKafka:
    def test_no_top_level_import_of_messaging_module(self):
        """app.core.messaging (which imports confluent_kafka) must only be
        imported lazily inside the INGEST_BACKEND == "kafka" branch of
        process_single_log, never at module load time -- otherwise every
        environment running the default sync path would need librdkafka
        installed just to import this router at all."""
        source = open(ingestion_module.__file__, encoding="utf-8").read()
        tree = ast.parse(source)
        top_level_imports = [
            node for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        for node in top_level_imports:
            module = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            assert "messaging" not in module and "confluent_kafka" not in names, (
                f"app.core.messaging/confluent_kafka must be imported lazily inside "
                f"the kafka branch, not at module level: found {ast.dump(node)}"
            )

    def test_ingestion_module_has_the_expected_entrypoint(self):
        assert hasattr(ingestion_module, "process_single_log")

    def test_default_backend_is_sync(self):
        from app.core.config import settings
        assert settings.INGEST_BACKEND == "sync"
