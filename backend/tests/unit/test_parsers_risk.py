"""Unit tests for parsers, format detector, and risk engine."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.parsers.format_detector import detect_format
from app.parsers.deterministic import parse_cef, parse_leef, parse_syslog, parse_json

# ─── Format Detection Tests ─────────────────────────────────────────────────

class TestFormatDetector:
    def test_detect_json(self):
        result = detect_format('{"src": "192.168.1.1", "dst": "10.0.0.1"}')
        assert result["format"] == "JSON"
        assert result["confidence"] == 1.0

    def test_detect_cef(self):
        log = "CEF:0|Vendor|Product|1.0|100|Event|5|src=1.2.3.4"
        result = detect_format(log)
        assert result["format"] == "CEF"
        assert result["confidence"] >= 0.99

    def test_detect_leef(self):
        log = "LEEF:2.0|Vendor|Product|1.0|10001|src=1.2.3.4"
        result = detect_format(log)
        assert result["format"] == "LEEF"

    def test_detect_syslog(self):
        log = "<134>Sep 22 16:45:32 host app: message"
        result = detect_format(log)
        assert result["format"] == "Syslog"

    def test_detect_unknown(self):
        log = "FW-D|22-09-2026|192.168.1.1>10.0.0.1|TCP|BLOCK"
        result = detect_format(log)
        assert result["format"] == "UNKNOWN"

    def test_detect_malformed_json_falls_through(self):
        log = '{"unclosed: bad json'
        result = detect_format(log)
        assert result["format"] != "JSON"

# ─── Parser Tests ───────────────────────────────────────────────────────────

class TestCEFParser:
    def test_valid_cef(self):
        log = "CEF:0|Palo Alto|PAN-OS|10.1|4000|Traffic Deny|7|src=192.168.1.20 dst=10.0.0.5 dpt=22 act=deny"
        result = parse_cef(log)
        assert result["header"]["vendor"] == "Palo Alto"
        assert result["header"]["severity"] == "7"
        assert "src" in result["fields"]
        assert result["fields"]["src"] == "192.168.1.20"

    def test_malformed_cef_returns_empty(self):
        result = parse_cef("CEF:0|OnlyOnePipe")
        assert result == {}

class TestSyslogParser:
    def test_valid_syslog(self):
        log = "<134>Sep 22 16:45:32 FW-001 kernel: message body here"
        result = parse_syslog(log)
        assert result["hostname"] == "FW-001"
        assert "message" in result

class TestJSONParser:
    def test_valid_json(self):
        import json
        data = {"src": "1.2.3.4", "action": "deny"}
        result = parse_json(json.dumps(data))
        assert result["src"] == "1.2.3.4"

    def test_invalid_json(self):
        result = parse_json("{bad json}")
        assert result == {}

# ─── Risk Engine Tests ───────────────────────────────────────────────────────

class TestRiskEngine:
    def test_critical_risk(self):
        from app.risk.engine import risk_engine
        from app.schemas.canonical import CanonicalEvent, EventDetails, Endpoint, NetworkDetails, DeviceDetails, ParserInfo, NormalizationInfo, ProvenanceInfo
        
        event = CanonicalEvent(
            event_id="test-001",
            timestamp="2026-09-22T16:00:00Z",
            event=EventDetails(category="authentication", type="change", action="malware", severity="critical", outcome="failure"),
            source=Endpoint(ip="10.0.0.1", port=1234),
            destination=Endpoint(ip="10.0.0.2", port=22),
            network=NetworkDetails(protocol="TCP"),
            device=DeviceDetails(vendor="Test"),
            parser=ParserInfo(format="JSON"),
            normalization=NormalizationInfo(mapping_method="deterministic", confidence=0.99),
            provenance=ProvenanceInfo(raw_event_id="raw-001", raw_sha256="abc123")
        )
        result = risk_engine.calculate_risk(event, correlation_score=80, frequency_score=60)
        assert result["score"] > 70
        assert result["level"] in ["HIGH", "CRITICAL"]
        assert "factors" in result
        assert len(result["factors"]) > 0

    def test_low_risk(self):
        from app.risk.engine import risk_engine
        from app.schemas.canonical import CanonicalEvent, EventDetails, Endpoint, NetworkDetails, DeviceDetails, ParserInfo, NormalizationInfo, ProvenanceInfo
        
        event = CanonicalEvent(
            event_id="test-002",
            timestamp="2026-09-22T16:00:00Z",
            event=EventDetails(category="network", type="connection", action="allow", severity="info", outcome="success"),
            source=Endpoint(ip="10.0.0.1", port=1234),
            destination=Endpoint(ip="10.0.0.2", port=80),
            network=NetworkDetails(protocol="TCP"),
            device=DeviceDetails(vendor="Test"),
            parser=ParserInfo(format="JSON"),
            normalization=NormalizationInfo(mapping_method="deterministic", confidence=0.99),
            provenance=ProvenanceInfo(raw_event_id="raw-002", raw_sha256="def456")
        )
        result = risk_engine.calculate_risk(event, correlation_score=0, frequency_score=0)
        assert result["score"] < 40
        assert result["level"] in ["LOW", "MEDIUM"]
