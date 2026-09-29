"""Classifies a normalized event's evidentiary weight using the distinction
between "we know nothing happened" (evidence of absence), "we don't have
enough to say" (insufficient data), and "something happened" (sufficient
evidence) -- as opposed to collapsing all three into one quality percentage.

A fourth category, "no_evidence", applies at the source level rather than
per-event: see detect_silent_sources in app/analytics/detection.py for that
case (a source that has gone quiet produces no events to classify at all).
"""

INSUFFICIENT_DATA_THRESHOLD = 40  # quality_score below this is too sparse to trust either way


def classify_epistemic_quality(quality_score: int, severity: str, outcome: str) -> dict:
    severity = (severity or "unknown").lower()
    outcome = (outcome or "unknown").lower()

    if quality_score < INSUFFICIENT_DATA_THRESHOLD:
        return {
            "category": "insufficient_data",
            "reason": f"only {quality_score}% of expected fields were populated (threshold {INSUFFICIENT_DATA_THRESHOLD}%) -- too sparse to conclude anything happened or didn't",
        }

    if severity in ("info", "low") and outcome in ("success", "unknown"):
        return {
            "category": "evidence_of_absence",
            "reason": "fields are well-populated and describe routine/benign activity -- positive evidence that nothing notable happened, not just missing data",
        }

    return {
        "category": "sufficient_evidence",
        "reason": "fields are well-populated and describe activity that warrants review",
    }
