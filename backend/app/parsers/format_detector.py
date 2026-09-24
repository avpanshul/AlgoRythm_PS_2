import json
import xml.etree.ElementTree as ET
import re

def detect_format(raw_log: str) -> dict:
    raw_log = raw_log.strip()
    
    # JSON
    if raw_log.startswith('{') and raw_log.endswith('}'):
        try:
            json.loads(raw_log)
            return {"format": "JSON", "confidence": 1.0, "detector": "json_detector"}
        except ValueError:
            pass

    # XML
    if raw_log.startswith('<') and raw_log.endswith('>'):
        try:
            ET.fromstring(raw_log)
            return {"format": "XML", "confidence": 1.0, "detector": "xml_detector"}
        except ET.ParseError:
            pass

    # CEF
    if "CEF:" in raw_log:
        return {"format": "CEF", "confidence": 0.99, "detector": "cef_detector"}

    # LEEF
    if "LEEF:" in raw_log:
        return {"format": "LEEF", "confidence": 0.99, "detector": "leef_detector"}

    # Syslog (RFC 3164 or 5424) -> typically starts with <PRI> e.g. <134>
    if re.match(r'^<\d{1,3}>', raw_log):
        return {"format": "Syslog", "confidence": 0.95, "detector": "syslog_detector"}

    # CSV (Heuristic: multiple commas, no spaces around commas, perhaps standard log headers)
    if ',' in raw_log and not raw_log.startswith('{') and not raw_log.startswith('<'):
        # Simple heuristic for demo
        parts = raw_log.split(',')
        if len(parts) > 3:
            return {"format": "CSV", "confidence": 0.70, "detector": "csv_detector"}

    return {"format": "UNKNOWN", "confidence": 0.0, "detector": "unknown_detector"}
