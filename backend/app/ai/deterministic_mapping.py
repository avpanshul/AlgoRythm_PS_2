"""Deterministic (non-LLM) field-name classification for recognized formats.

Item 1 (LLM reliability): a live audit found pack drafting produced 0% real
field mappings in this project's own dev/demo environment -- not because the
architecture is wrong, but because the local Ollama model was misconfigured
(wrong default name) and, even fixed, real CPU-only inference reliably
exceeded the request timeout. An LLM is genuinely useful for a field name
this table has never seen, but for the common, well-known field names real
vendors actually use in KeyValue/JSON/CEF logs (src_ip, user, action, ...),
asking a slow, occasionally-unavailable model to reinvent that lookup every
single time is real fragility for no real benefit. This module is that
lookup, run BEFORE the LLM is even called -- it's the deterministic fallback
in app/services/pack_drafting.py:classify_sample_fields, and by design it's
consulted for every field regardless of whether the LLM would have been
available, since a correct deterministic answer is strictly better than an
LLM call that might time out.

Scope, honestly stated: this only recognizes common English field-name
aliases. It will not classify a vendor-specific or non-English field name --
that's exactly the case the LLM path (or Item 5's refine loop) is still for.
"""
import re

# canonical_field -> exact, lowercased, alnum-only raw field names it matches.
# Sourced from real, common vendor field-naming conventions (syslog KeyValue,
# CEF extension keys, common JSON log shapes) -- not an invented taxonomy.
_ALIASES = {
    "source.ip": {"srcip", "sourceip", "src", "saddr", "clientip", "sip", "sourceaddress"},
    "source.port": {"srcport", "sourceport", "sport", "sp"},
    "destination.ip": {"dstip", "destip", "destinationip", "dst", "daddr", "targetip", "dip", "destinationaddress"},
    "destination.port": {"dstport", "destport", "destinationport", "dport", "dp"},
    "event.action": {"action", "eventaction", "activity", "verb", "cmd", "command"},
    "event.category": {"category", "eventcategory", "class", "cat"},
    "event.type": {"type", "eventtype", "evttype", "logtype"},
    "event.severity": {"severity", "sev", "priority", "level", "loglevel"},
    "event.outcome": {"outcome", "result", "status", "disposition"},
    "network.protocol": {"proto", "protocol", "networkprotocol", "ipproto"},
    "network.transport": {"transport", "networktransport", "l4proto"},
    "user.name": {"user", "username", "usrname", "usr", "account", "uid", "accountname", "loginuser"},
    "device.id": {"deviceid", "devid", "hostid", "assetid"},
    "device.vendor": {"vendor", "devicevendor", "manufacturer", "vendorname"},
    "device.product": {"product", "deviceproduct", "app", "application", "productname"},
    "timestamp": {"ts", "time", "timestamp", "datetime", "date", "eventtime", "occurred", "occurredat"},
}

# Formats where the deterministic parser reliably splits the line into real,
# individually-named fields (so a raw_field name is meaningful to alias-match
# against). "UNKNOWN"/anything else falls through to a single "raw" blob --
# there's nothing here for this table to classify.
#
# CSV included since pack_drafting.py's wizard-preview path now uses a real
# header row (when the pasted sample has one) to name fields, same as
# KeyValue/JSON/CEF -- real per-event CSV ingestion still names fields
# positionally (no header on a single line), so classify_field_deterministic
# just correctly finds no alias match there, same as any other unrecognized
# name; this doesn't change that behavior.
DETERMINISTIC_ELIGIBLE_FORMATS = {"KeyValue", "JSON", "CEF", "CSV"}


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def classify_field_deterministic(raw_field: str, format_type: str) -> dict | None:
    """Returns a classification dict in the same shape LLMReasoner.ask_mapping
    returns (selected_field/confidence/reason), or None if this field name
    isn't a recognized alias -- callers fall back to the LLM on None, never
    on a low-confidence guess (this never guesses; it only ever returns an
    exact, table-backed match or nothing)."""
    if format_type not in DETERMINISTIC_ELIGIBLE_FORMATS:
        return None
    key = _normalize(raw_field)
    if not key:
        return None
    for canonical_field, aliases in _ALIASES.items():
        if key in aliases:
            return {
                "selected_field": canonical_field,
                "confidence": 1.0,
                "reason": f"deterministic alias match: '{raw_field}' -> '{canonical_field}' (known {format_type} field name, no LLM call needed)",
            }
    return None
