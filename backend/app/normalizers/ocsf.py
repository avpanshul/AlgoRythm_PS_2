"""Best-effort mapping from this pipeline's ECS-like canonical event onto OCSF
1.x class/category/severity identifiers.

This is NOT an OCSF compliance claim -- it maps the handful of category/severity
values the pipeline currently produces (network, authentication, system,
unknown; info/low/medium/high/critical) onto the closest documented OCSF 1.x
identifiers, and falls back to the generic "Base Event" class (class_uid 0)
for anything else. `type_uid` follows OCSF's documented formula
(class_uid * 100 + activity_id); the class/category/severity IDs below were
taken from the published OCSF 1.x schema (schema.ocsf.io) but this mapping
covers only this pipeline's current category vocabulary -- verify against the
current schema before asserting compliance in any real submission.
"""

# event_data["category"] -> (class_uid, class_name, category_uid, category_name)
_CATEGORY_MAP = {
    "network": (4001, "Network Activity", 4, "Network Activity"),
    "authentication": (3002, "Authentication", 3, "Identity & Access Management"),
    "system": (1001, "File System Activity", 1, "System Activity"),
}

_SEVERITY_MAP = {
    "info": 1, "low": 2, "medium": 3, "high": 4, "critical": 5, "unknown": 0,
}

_BASE_EVENT = (0, "Base Event", 0, "Uncategorized")


def to_ocsf(event_data: dict) -> dict:
    event_data = event_data or {}
    category = event_data.get("category", "unknown")
    severity = event_data.get("severity", "unknown")

    class_uid, class_name, category_uid, category_name = _CATEGORY_MAP.get(category, _BASE_EVENT)
    severity_id = _SEVERITY_MAP.get(severity, 0)
    activity_id = 0  # OCSF activity_id is class-specific; this pipeline doesn't
                      # yet resolve a per-class activity, so it's left generic.

    return {
        "class_uid": class_uid,
        "class_name": class_name,
        "category_uid": category_uid,
        "category_name": category_name,
        "severity_id": severity_id,
        "activity_id": activity_id,
        "type_uid": class_uid * 100 + activity_id,
        "metadata": {"version": "1.1.0", "product": {"name": "ULPF", "vendor_name": "ULPF"}},
    }
