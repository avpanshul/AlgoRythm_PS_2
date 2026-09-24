import json
import re
import xml.etree.ElementTree as ET

def parse_json(raw_log: str) -> dict:
    try:
        return json.loads(raw_log)
    except Exception:
        return {}

def parse_cef(raw_log: str) -> dict:
    # CEF:Version|Device Vendor|Device Product|Device Version|Signature ID|Name|Severity|[Extension]
    parts = raw_log.split('|')
    if len(parts) < 8:
        return {}
    
    header = {
        "vendor": parts[1],
        "product": parts[2],
        "device_version": parts[3],
        "signature_id": parts[4],
        "name": parts[5],
        "severity": parts[6]
    }
    
    extension_str = '|'.join(parts[7:])
    fields = {}
    
    # Simple regex to split CEF extension: key=value
    ext_matches = re.findall(r'([a-zA-Z0-9]+)=([^=]+)(?=\s+[a-zA-Z0-9]+=|$)', extension_str)
    for k, v in ext_matches:
        fields[k.strip()] = v.strip()
        
    return {"header": header, "fields": fields}

def parse_leef(raw_log: str) -> dict:
    # LEEF:Version|Vendor|Product|Version|EventID|Delimiter|[Extension]
    parts = raw_log.split('|')
    if len(parts) < 6:
        return {}
        
    header = {
        "vendor": parts[1],
        "product": parts[2],
        "version": parts[3],
        "event_id": parts[4]
    }
    
    delimiter = parts[5]
    if not delimiter:
        delimiter = '\t'
        
    extension_str = '|'.join(parts[6:])
    fields = {}
    
    for kv in extension_str.split(delimiter):
        if '=' in kv:
            k, v = kv.split('=', 1)
            fields[k.strip()] = v.strip()
            
    return {"header": header, "fields": fields}

def parse_syslog(raw_log: str) -> dict:
    # <PRI>TIMESTAMP HOSTNAME APP-NAME PROCID MSGID [SD-ID] MSG
    # Simplified regex for demo
    match = re.match(r'^<(\d+)>([A-Z][a-z]{2}\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(.*)', raw_log)
    if match:
        return {
            "pri": match.group(1),
            "timestamp": match.group(2),
            "hostname": match.group(3),
            "message": match.group(4)
        }
    return {"message": raw_log}

def parse_xml(raw_log: str) -> dict:
    try:
        root = ET.fromstring(raw_log)
        # Convert simple XML to dict
        def etree_to_dict(t):
            d = {t.tag: {} if t.attrib else None}
            children = list(t)
            if children:
                dd = {}
                for dc in map(etree_to_dict, children):
                    for k, v in dc.items():
                        dd[k] = v
                d = {t.tag: dd}
            if t.attrib:
                d[t.tag].update(('@' + k, v) for k, v in t.attrib.items())
            if t.text and t.text.strip():
                if children or t.attrib:
                    d[t.tag]['#text'] = t.text.strip()
                else:
                    d[t.tag] = t.text.strip()
            return d
        return etree_to_dict(root)
    except Exception:
        return {}

def parse_csv(raw_log: str) -> dict:
    parts = raw_log.split(',')
    return {f"field_{i}": p.strip() for i, p in enumerate(parts)}

def parse_log(raw_log: str, format_type: str) -> dict:
    if format_type == "JSON":
        return parse_json(raw_log)
    elif format_type == "CEF":
        return parse_cef(raw_log)
    elif format_type == "LEEF":
        return parse_leef(raw_log)
    elif format_type == "Syslog":
        return parse_syslog(raw_log)
    elif format_type == "XML":
        return parse_xml(raw_log)
    elif format_type == "CSV":
        return parse_csv(raw_log)
    else:
        return {"raw": raw_log}
