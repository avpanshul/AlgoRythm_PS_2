"""Minimal RFC 8785 (JSON Canonicalization Scheme) serializer.

Covers the JSON value space this pipeline's canonical event dict actually
produces: strings, ints, bools, None, and nested dicts/lists (no floats -- risk
scores, ports, etc. are ints). JCS's two rules that diverge from a plain
`json.dumps(sort_keys=True)` are (1) object keys sorted by UTF-16 code unit and
(2) ECMA-262 number-to-string formatting for floats. (1) is implemented below;
(2) does not apply since no floats occur in canonical events -- if one ever did,
`json.dumps` would emit Python float repr, not the ECMA format, so this is a
known, narrow limitation rather than a full JCS implementation for arbitrary JSON.
"""
import json


def _sort_key(s: str):
    # Compare by UTF-16 code unit, per RFC 8785 section 3.2.3. Python's default
    # string ordering (by code point) already matches this for the BMP, which is
    # everything our field names and values fall into.
    return [ord(c) for c in s]


def _canonicalize(value):
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value.keys(), key=_sort_key)}
    if isinstance(value, list):
        return [_canonicalize(v) for v in value]
    return value


def canonicalize(obj) -> str:
    """Serialize `obj` per RFC 8785: sorted object keys, no insignificant
    whitespace, no ASCII-escaping of non-ASCII text."""
    return json.dumps(_canonicalize(obj), ensure_ascii=False, separators=(",", ":"))
