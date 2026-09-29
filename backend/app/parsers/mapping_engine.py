r"""Executes a published Parser's YAML/JSON field-mapping config ("source pack")
against a parsed log's fields, so a source pack is actually run by the live
pipeline instead of only being stored for display.

Config schema (Parser.config_json):

    field_mappings:
      - raw_field: fields.src          # dotted path into the parsed dict, OR
        canonical_field: source_ip     # dotted path into the canonical event dict
      - raw_field: [fields.suser, fields.duser]   # a list of candidate paths
        canonical_field: user_name
        list_mode: coalesce            # coalesce (default): first non-null wins
      - raw_field: fields.cs_list      # a raw_field that is itself a list value
        canonical_field: message
        list_mode: join                # join all elements into one string
        join_delimiter: ", "
      - raw_field: message             # free-text extraction (e.g. Cisco ASA/pfSense
        canonical_field: source_ip     # syslog messages, where the real fields are
        regex: 'outside:(\d{1,3}(?:\.\d{1,3}){3})'   # embedded in prose, not key=value)
        regex_group: 1                 # named or numbered group; defaults to 1
    static:
      device_vendor: PaloAlto          # constants applied regardless of parsed content
"""
import re
from typing import Any


def _get_path(d: Any, path: str) -> Any:
    # A literal top-level key containing a dot (e.g. Zeek's own field names,
    # id.orig_h/id.resp_h) takes priority over dotted-path traversal -- if the
    # exact string is a real key, it's not meant to be split into segments.
    if isinstance(d, dict) and path in d:
        return d[path]

    cur = d
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _set_path(d: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = d
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def _first_non_empty(values: list) -> Any:
    for v in values:
        if v not in (None, "", []):
            return v
    return None


def _resolve_value(parsed: dict, mapping: dict) -> Any:
    raw_field = mapping.get("raw_field")
    list_mode = mapping.get("list_mode", "coalesce")
    join_delim = mapping.get("join_delimiter", ", ")

    if isinstance(raw_field, list):
        # Multiple candidate source paths -- coalesce (first present) or join them.
        values = [_get_path(parsed, p) for p in raw_field]
        if list_mode == "join":
            present = [str(v) for v in values if v not in (None, "", [])]
            return join_delim.join(present) if present else None
        return _first_non_empty(values)

    if not raw_field:
        return None

    value = _get_path(parsed, raw_field)

    regex = mapping.get("regex")
    if regex and isinstance(value, str):
        # Extraction from free text (a syslog message body, not a structured
        # key=value/JSON field) -- the only way to field-map vendors whose log
        # format embeds real fields in prose (Cisco ASA, pfSense filterlog).
        match = re.search(regex, value)
        if not match:
            return None
        group = mapping.get("regex_group", 1)
        try:
            return match.group(group)
        except IndexError:
            # re.Match.group() raises IndexError for both a bad numeric group
            # and a named group that doesn't exist in the pattern.
            return None

    if isinstance(value, list):
        # A single raw field whose parsed value is itself a list (e.g. a
        # repeated CEF/JSON key) -- same coalesce/join choice applies.
        if list_mode == "join":
            return join_delim.join(str(v) for v in value if v not in (None, ""))
        return _first_non_empty(value)

    return value


def apply_source_pack(parsed: dict, config_json: dict) -> dict:
    """Run a source pack's `static` values and `field_mappings` against `parsed`.
    Returns a nested dict shaped like the canonical event (e.g. {"source_ip": ...,
    "event_data": {"action": ...}})."""
    result: dict = {}
    if not config_json:
        return result

    for key, value in (config_json.get("static") or {}).items():
        _set_path(result, key, value)

    for mapping in (config_json.get("field_mappings") or []):
        canonical_field = mapping.get("canonical_field")
        if not canonical_field:
            continue
        value = _resolve_value(parsed, mapping)
        if value is not None:
            _set_path(result, canonical_field, value)

    return result
