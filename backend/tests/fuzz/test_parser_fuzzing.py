r"""Fuzz tests for every log decoder (ULPF-master-prompt.md D6/C8: "fuzz
every decoder... put results in CI"). Property under test, for every
decoder: **no adversarial input crashes the process** -- a parser may
return an empty/partial result for garbage input, it may never raise an
unhandled exception. That's the actual security property "hostile-input
handling" means: a malicious or malformed log line is attacker-controlled
input, and this pipeline processes untrusted logs by definition.

Uses Hypothesis (property-based testing, not hand-picked edge cases) so the
input space actually explored is large and reproducible -- a failure prints
a minimal failing example and is replayable via Hypothesis's own example
database.

Run standalone: `pytest tests/fuzz/ -q` (separate from tests/unit/ so a slow
CI fuzz stage can be run independently -- see the new .github workflow).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from hypothesis import given, settings, strategies as st, HealthCheck

from app.parsers.deterministic import (
    parse_json, parse_cef, parse_leef, parse_syslog, parse_xml, parse_csv, parse_key_value, parse_log,
)
from app.parsers.format_detector import detect_format
from app.core.processing import normalize_parsed_data, redact_pii

# Printable text plus the specific bytes real hostile input actually uses:
# null bytes, control characters, and log-injection payloads (CRLF, ANSI
# escapes) -- not just "random unicode", which real attacker input rarely
# is, but the union covers both.
_HOSTILE_TEXT = st.one_of(
    st.text(min_size=0, max_size=2000),
    st.text(alphabet=st.characters(min_codepoint=0, max_codepoint=0x10ffff), min_size=0, max_size=500),
    st.binary(min_size=0, max_size=500).map(lambda b: b.decode("utf-8", errors="replace")),
)

_SUPPRESSED_HEALTH_CHECKS = [HealthCheck.too_slow, HealthCheck.data_too_large]


class TestFormatDetectorFuzzing:
    @given(_HOSTILE_TEXT)
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_detect_format_never_crashes(self, raw):
        result = detect_format(raw)
        assert isinstance(result, dict)
        assert "format" in result


class TestJsonFuzzing:
    @given(_HOSTILE_TEXT)
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_parse_json_never_crashes(self, raw):
        result = parse_json(raw)
        assert isinstance(result, dict)


class TestCefFuzzing:
    @given(_HOSTILE_TEXT)
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_parse_cef_never_crashes(self, raw):
        result = parse_cef(raw)
        assert isinstance(result, dict)

    @given(st.text(alphabet="CEF:|0123456789 =\\", min_size=0, max_size=300))
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_parse_cef_never_crashes_on_cef_shaped_garbage(self, raw):
        """Adversarial input shaped *like* CEF (right alphabet/delimiters,
        wrong structure) is the more realistic attack than pure noise --
        malformed pipe counts, unbalanced escapes, empty fields."""
        result = parse_cef(raw)
        assert isinstance(result, dict)


class TestLeefFuzzing:
    @given(_HOSTILE_TEXT)
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_parse_leef_never_crashes(self, raw):
        result = parse_leef(raw)
        assert isinstance(result, dict)


class TestSyslogFuzzing:
    @given(_HOSTILE_TEXT)
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_parse_syslog_never_crashes(self, raw):
        result = parse_syslog(raw)
        assert isinstance(result, dict)

    @given(st.text(alphabet="<>0123456789 :", min_size=0, max_size=200))
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_parse_syslog_never_crashes_on_malformed_pri(self, raw):
        """PRI parsing (<NNN>) is the classic place an off-by-one or int()
        cast crashes on a malformed/oversized/negative priority value."""
        result = parse_syslog(raw)
        assert isinstance(result, dict)


class TestXmlFuzzing:
    @given(_HOSTILE_TEXT)
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_parse_xml_never_crashes(self, raw):
        result = parse_xml(raw)
        assert isinstance(result, dict)

    @given(st.text(alphabet="<>/= \"abc123", min_size=0, max_size=400))
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_parse_xml_never_crashes_on_malformed_tags(self, raw):
        """Unbalanced/malformed tags -- the actual shape of a hostile XML
        payload, not just random text -- must not crash the XML parser or
        (a real historical risk class for XML parsers generally) hang on
        entity expansion. This project's parser doesn't resolve external
        entities at all, which is the correct defense against XXE."""
        result = parse_xml(raw)
        assert isinstance(result, dict)

    def test_xml_external_entity_is_not_resolved(self):
        """A concrete XXE probe: if this ever starts reading local files or
        making network calls via an external entity, this is exactly the
        vulnerability class D6's fuzzing requirement exists to catch."""
        payload = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            '<root>&xxe;</root>'
        )
        result = parse_xml(payload)
        # Whatever comes back, it must not contain resolved file content.
        assert "root:" not in str(result)  # a canary that would appear if /etc/passwd got inlined


class TestCsvFuzzing:
    @given(_HOSTILE_TEXT)
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_parse_csv_never_crashes(self, raw):
        result = parse_csv(raw)
        assert isinstance(result, dict)


class TestKeyValueFuzzing:
    @given(_HOSTILE_TEXT)
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_parse_key_value_never_crashes(self, raw):
        result = parse_key_value(raw)
        assert isinstance(result, dict)

    @given(st.text(alphabet="abc=\" 0123456789", min_size=0, max_size=300))
    @settings(max_examples=300, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_parse_key_value_never_crashes_on_malformed_pairs(self, raw):
        result = parse_key_value(raw)
        assert isinstance(result, dict)


class TestFullPipelineFuzzing:
    """The end-to-end property: detect -> parse -> normalize must never
    crash regardless of what format detection guesses, even when the
    guessed format doesn't actually match the content (a real scenario --
    detection is heuristic, not guaranteed correct)."""

    @given(_HOSTILE_TEXT)
    @settings(max_examples=200, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_detect_parse_normalize_never_crashes(self, raw):
        detection = detect_format(raw)
        fmt = detection["format"]
        if fmt == "UNKNOWN":
            return  # routed to Drain3/DLQ elsewhere, not this pipeline's job
        try:
            parsed = parse_log(raw, fmt)
        except Exception as e:
            raise AssertionError(f"parse_log crashed on format={fmt!r} raw={raw!r}: {e}")
        if not parsed or parsed == {}:
            return
        try:
            normalized = normalize_parsed_data(parsed, fmt, raw)
        except Exception as e:
            raise AssertionError(f"normalize_parsed_data crashed on format={fmt!r} parsed={parsed!r}: {e}")
        assert isinstance(normalized, dict)
        assert "event_data" in normalized

    @given(_HOSTILE_TEXT)
    @settings(max_examples=200, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS, deadline=None)
    def test_pii_redaction_never_crashes(self, raw):
        redacted, fields = redact_pii(raw)
        assert isinstance(redacted, str)
        assert isinstance(fields, list)
