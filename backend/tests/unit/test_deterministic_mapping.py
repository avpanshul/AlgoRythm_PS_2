"""Tests for Item 1 (LLM reliability): deterministic field-name classification
that runs before any LLM call, for recognized formats (KeyValue/JSON/CEF)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.ai.deterministic_mapping import classify_field_deterministic


class TestDeterministicClassification:
    def test_known_alias_matches_in_keyvalue(self):
        result = classify_field_deterministic("src_ip", "KeyValue")
        assert result is not None
        assert result["selected_field"] == "source.ip"
        assert result["confidence"] == 1.0

    def test_known_alias_case_and_punctuation_insensitive(self):
        result = classify_field_deterministic("Src-IP", "KeyValue")
        assert result is not None
        assert result["selected_field"] == "source.ip"

    def test_known_alias_matches_in_json_and_cef_too(self):
        for fmt in ("JSON", "CEF"):
            result = classify_field_deterministic("user", fmt)
            assert result is not None
            assert result["selected_field"] == "user.name"

    def test_unrecognized_field_name_returns_none(self):
        assert classify_field_deterministic("some_totally_custom_vendor_field_xyz", "KeyValue") is None

    def test_ineligible_format_returns_none_even_for_a_known_alias(self):
        # "UNKNOWN"-format lines are a single unstructured blob (see
        # pack_drafting.py) -- a raw_field name isn't meaningful there, so
        # this table must never claim a match for it.
        assert classify_field_deterministic("src_ip", "UNKNOWN") is None
        assert classify_field_deterministic("src_ip", "Syslog") is None

    def test_empty_field_name_returns_none(self):
        assert classify_field_deterministic("", "KeyValue") is None
        assert classify_field_deterministic("___", "KeyValue") is None

    def test_multiple_distinct_canonical_fields_covered(self):
        cases = {
            "dst_port": "destination.port",
            "action": "event.action",
            "severity": "event.severity",
            "proto": "network.protocol",
            "vendor": "device.vendor",
            "timestamp": "timestamp",
        }
        for raw, expected in cases.items():
            result = classify_field_deterministic(raw, "JSON")
            assert result is not None, f"expected a match for {raw!r}"
            assert result["selected_field"] == expected
