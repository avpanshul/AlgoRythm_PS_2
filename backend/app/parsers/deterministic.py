import json
import re
import xml.etree.ElementTree as ET

def parse_json(raw_log: str) -> dict:
    """Real bug found by fuzz testing (Part D6/C8): a JSON *document* that's
    valid but not an *object* -- a bare `true`/`false`/`null`/number/string,
    or a top-level array -- parses successfully via json.loads() but isn't a
    dict, and every caller of this function assumes a dict (calls .get() on
    it). Treated the same as a parse failure (empty dict), not propagated as
    a non-dict value that would crash downstream with an AttributeError on
    genuinely hostile-but-technically-valid-JSON input."""
    try:
        result = json.loads(raw_log)
    except Exception:
        return {}
    return result if isinstance(result, dict) else {}

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
    # RFC 3164 BSD syslog with no <PRI> header -- real, very common in
    # practice (e.g. OpenSSH logging through the system syslog daemon):
    # "Dec 10 06:55:46 LabSZ sshd[24200]: message"
    bsd_match = re.match(r'^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(.*)', raw_log)
    if bsd_match:
        return {
            "timestamp": bsd_match.group(1),
            "hostname": bsd_match.group(2),
            "message": bsd_match.group(3),
        }
    return {"message": raw_log}


def parse_hdfs_log(raw_log: str) -> dict:
    """HDFS/Hadoop daemon log line: "YYMMDD HHMMSS PID LEVEL component: message"."""
    match = re.match(r'^(\d{6})\s+(\d{6})\s+(\d+)\s+([A-Z]+)\s+([\w.$]+):\s*(.*)$', raw_log)
    if not match:
        return {}
    date_str, time_str, pid, level, component, message = match.groups()
    return {
        "date": date_str, "time": time_str, "pid": pid,
        "level": level, "component": component, "message": message,
    }


def parse_hpc_log(raw_log: str) -> dict:
    """HPC/BlueGene-style node event: "id node subsystem event_type unix_ts flag message"."""
    match = re.match(r'^(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d{9,10})\s+(-?\d+)\s+(.*)$', raw_log)
    if not match:
        return {}
    event_id, node, subsystem, event_type, ts, flag, message = match.groups()
    return {
        "event_id": event_id, "node": node, "subsystem": subsystem,
        "event_type": event_type, "unix_timestamp": ts, "flag": flag, "message": message,
    }


def parse_log4j_log(raw_log: str) -> dict:
    """Log4j-pattern daemon log (Hadoop YARN / Zookeeper / many Java services):
    "TIMESTAMP LEVEL [thread] logger: message" or the Zookeeper dashed
    variant "TIMESTAMP - LEVEL [thread] - message" (no separate logger)."""
    match = re.match(
        r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+-?\s*([A-Z]+)\s+\[([^\]]*)\]\s*-?\s*(?:([\w.$]+):)?\s*(.*)$',
        raw_log)
    if not match:
        return {}
    ts_str, level, thread, logger, message = match.groups()
    return {
        "timestamp": ts_str, "level": level, "thread": thread,
        "logger": logger, "message": message,
    }


def parse_bgl_log(raw_log: str) -> dict:
    """BlueGene/L (BGL) RAS event log, the canonical loghub BGL format:
    "label unix_ts date node iso_time node_repeat type component level content"."""
    match = re.match(
        r'^(\S+)\s+(\d{9,10})\s+(\d{4}\.\d{2}\.\d{2})\s+(\S+)\s+(\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}\.\d+)\s+(\S+)\s+(\w+)\s+(\w+)\s+(\w+)\s+(.*)$',
        raw_log)
    if not match:
        return {}
    label, unix_ts, date_str, node, iso_time, node_repeat, event_type, component, level, message = match.groups()
    return {
        "label": label, "unix_timestamp": unix_ts, "node": node,
        "event_type": event_type, "component": component, "level": level, "message": message,
    }


def parse_apache_error_log(raw_log: str) -> dict:
    """Apache httpd error log: "[Day Mon DD HH:MM:SS YYYY] [level] message"."""
    match = re.match(r'^\[(\w{3} \w{3} \d{1,2} \d{2}:\d{2}:\d{2} \d{4})\]\s+\[(\w+)\]\s*(.*)$', raw_log)
    if not match:
        return {}
    ts_str, level, message = match.groups()
    return {"timestamp": ts_str, "level": level, "message": message}


def parse_windows_trace_log(raw_log: str) -> dict:
    """Windows CBS/trace log: "YYYY-MM-DD HH:MM:SS, Level  Component  message"."""
    match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\s+(\w+)\s+(\S+)\s+(.*)$', raw_log)
    if not match:
        return {}
    ts_str, level, component, message = match.groups()
    return {"timestamp": ts_str, "level": level, "component": component, "message": message}

def parse_xml(raw_log: str) -> dict:
    try:
        root = ET.fromstring(raw_log)
        # Convert simple XML to dict. Sibling elements sharing a tag name (e.g.
        # Windows Event Log's repeated <Data Name="X">value</Data> under
        # <EventData>) are collected into a list rather than overwriting each
        # other -- a single-child tag stays a plain dict, unchanged, so this is
        # backward compatible with formats that never repeat a tag.
        def etree_to_dict(t):
            d = {t.tag: {} if t.attrib else None}
            children = list(t)
            if children:
                dd = {}
                for child, dc in zip(children, map(etree_to_dict, children)):
                    for k, v in dc.items():
                        if k in dd:
                            if not isinstance(dd[k], list):
                                dd[k] = [dd[k]]
                            dd[k].append(v)
                        else:
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

def parse_key_value(raw_log: str) -> dict:
    """Parses space-separated key=value / key="quoted value" pairs, e.g.
    FortiGate: `date=2026-09-24 time=10:00:00 srcip=1.2.3.4 dstip=5.6.7.8 action=deny`."""
    pairs = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)=(?:"([^"]*)"|(\S+))', raw_log)
    return {k: (quoted if quoted else unquoted) for k, quoted, unquoted in pairs}

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
    elif format_type == "KeyValue":
        return parse_key_value(raw_log)
    elif format_type == "HDFSLog":
        return parse_hdfs_log(raw_log)
    elif format_type == "HPCLog":
        return parse_hpc_log(raw_log)
    elif format_type == "ApacheErrorLog":
        return parse_apache_error_log(raw_log)
    elif format_type == "WindowsTraceLog":
        return parse_windows_trace_log(raw_log)
    elif format_type == "Log4jLog":
        return parse_log4j_log(raw_log)
    elif format_type == "BGLLog":
        return parse_bgl_log(raw_log)
    else:
        return {"raw": raw_log}
