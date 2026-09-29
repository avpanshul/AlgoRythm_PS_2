"""Regression tests for the experimental event-risk classifier
(app/ai/event_classifier.py, app/ai/models/event_risk_classifier.json).

These pin two things: the timestamp/protocol normalization helpers it
depends on indirectly are not exercised here (see test_integrity.py) --
this file is specifically about not letting the classifier's honest
"experimental, not integrated" status silently disappear, and about
re-asserting the real-data confound that caused that status, so nobody
re-enables it later without re-litigating the actual finding.
See docs/ML_EVENT_CLASSIFIER.md for the full investigation.
"""
import json
import os

from app.ai import event_classifier

_ARTIFACT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "app", "ai", "models", "event_risk_classifier.json"
)

# Real, documented-benign Windows Event Log XML (Event ID 5157 -- "Windows
# Filtering Platform blocked a connection"), field values from
# ultimatewindowssecurity.com's own reference example -- the same sample the
# `windows_firewall_xml` vendor pack uses. Not from the attack-sample corpus.
_REAL_BENIGN_WINDOWS_XML = (
    '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
    '<System><Provider Name="Microsoft-Windows-Windows Firewall With Advanced Security"/>'
    '<EventID>5157</EventID><Level>0</Level><Task>12810</Task>'
    '<TimeCreated SystemTime="2026-09-24T10:00:00.000000000Z"/>'
    '<Computer>WORKSTATION.contoso.local</Computer></System>'
    '<EventData><Data Name="ProcessID">1224</Data>'
    r'<Data Name="Application">\device\harddiskvolume1\windows\system32\svchost.exe</Data>'
    '<Data Name="Direction">%%14592</Data>'
    '<Data Name="SourceAddress">224.0.0.252</Data><Data Name="SourcePort">5355</Data>'
    '<Data Name="DestAddress">10.45.45.102</Data><Data Name="DestPort">56927</Data>'
    '<Data Name="Protocol">17</Data>'
    '<Data Name="FilterRTID">0</Data><Data Name="LayerName">%%14611</Data>'
    '<Data Name="LayerRTID">44</Data></EventData></Event>'
)


class TestEventClassifierStatus:
    def test_artifact_is_marked_experimental_not_integrated(self):
        """If this ever flips, it must be because someone fixed the actual
        confound documented below (with new real data), not because the
        status field was edited to make the model look shippable."""
        with open(_ARTIFACT_PATH, encoding="utf-8") as f:
            artifact = json.load(f)
        assert artifact["model_card"]["status"] == "experimental_not_integrated"

    def test_not_wired_into_processing_pipeline(self):
        """The live pipeline must not import or call the classifier until
        the confound below is actually resolved with real data."""
        import app.core.processing as processing
        assert "event_classifier" not in open(processing.__file__, encoding="utf-8").read()


class TestEventClassifierConfound:
    """Confirms the classifier is still confounded by log format rather than
    malice -- documents why it stays unintegrated, and would fail loudly if
    someone retrained it without fixing the underlying data problem."""

    def test_confidently_misclassifies_real_benign_windows_event(self):
        if not event_classifier.is_available():
            return  # artifact not built in this environment; nothing to check
        result = event_classifier.score(_REAL_BENIGN_WINDOWS_XML)
        assert result is not None
        # This assertion is intentionally the *bad* outcome: it documents
        # that the model still gets this wrong, not that it should.
        assert result["label"] == "malicious"
        assert result["probability_malicious"] > 0.9

    def test_correctly_scores_real_benign_non_windows_log(self):
        if not event_classifier.is_available():
            return
        result = event_classifier.score(
            "kernel[0]: AirPort: Link Up on awdl0"  # real loghub line shape
        )
        assert result is not None
        assert result["label"] == "benign"
