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

    # HDFS/Hadoop daemon log: "081109 203807 222 INFO dfs.DataNode$PacketResponder: message"
    if re.match(r'^\d{6}\s+\d{6}\s+\d+\s+[A-Z]+\s+[\w.$]+:', raw_log):
        return {"format": "HDFSLog", "confidence": 0.9, "detector": "hdfs_detector"}

    # Log4j-pattern daemon log (Hadoop YARN / Zookeeper / many Java services):
    # "2015-10-18 18:01:50,353 INFO [main] org.apache...MRAppMaster: message" or
    # "2015-07-29 19:27:55,066 - INFO  [thread] - message" (Zookeeper's dashed variant)
    if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\s+-?\s*[A-Z]+\s+\[[^\]]*\]', raw_log):
        return {"format": "Log4jLog", "confidence": 0.9, "detector": "log4j_detector"}

    # BlueGene/L (BGL) RAS event log, the canonical loghub BGL format:
    # "<label> <unix_ts> <YYYY.MM.DD> <node> <iso_time> <node> <type> <component> <level> message"
    if re.match(r'^\S+\s+\d{9,10}\s+\d{4}\.\d{2}\.\d{2}\s+\S+\s+\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}\.\d+\s+\S+\s+\w+\s+\w+\s+\w+\s+', raw_log):
        return {"format": "BGLLog", "confidence": 0.9, "detector": "bgl_detector"}

    # HPC/BlueGene node event: "344518 node-246 unix.hw state_change.unavailable 1084270955 1 message"
    if re.match(r'^\d+\s+\S+\s+\S+\s+\S+\s+\d{9,10}\s+-?\d+\s+', raw_log):
        return {"format": "HPCLog", "confidence": 0.85, "detector": "hpc_detector"}

    # Apache httpd error log: "[Sun Dec 04 04:47:44 2005] [notice] message"
    if re.match(r'^\[\w{3} \w{3} \d{1,2} \d{2}:\d{2}:\d{2} \d{4}\]\s+\[\w+\]', raw_log):
        return {"format": "ApacheErrorLog", "confidence": 0.9, "detector": "apache_error_detector"}

    # Windows CBS/trace log: "2016-09-28 04:30:31, Info    CSI    message"
    if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\s+\w+\s+\S+', raw_log):
        return {"format": "WindowsTraceLog", "confidence": 0.85, "detector": "windows_trace_detector"}

    # Syslog RFC 3164 (BSD-style), no <PRI> header -- extremely common in
    # practice (e.g. OpenSSH logging via the system syslog daemon):
    # "Dec 10 06:55:46 LabSZ sshd[24200]: message"
    if re.match(r'^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\S+\s+\S+:', raw_log):
        return {"format": "Syslog", "confidence": 0.85, "detector": "syslog_bsd_detector"}

    # CSV (Heuristic: multiple commas, no spaces around commas, perhaps standard log headers)
    if ',' in raw_log and not raw_log.startswith('{') and not raw_log.startswith('<'):
        # Simple heuristic for demo
        parts = raw_log.split(',')
        if len(parts) > 3:
            return {"format": "CSV", "confidence": 0.70, "detector": "csv_detector"}

    # KEY_VALUE (e.g. FortiGate: date=2026-09-24 time=10:00:00 srcip=1.2.3.4 action=deny) --
    # a run of space-separated key=value (or key="quoted value") tokens covering most
    # of the line, with no CEF:/LEEF: prefix and no comma-delimited structure.
    kv_tokens = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*="[^"]*"|\b[a-zA-Z_][a-zA-Z0-9_]*=\S+', raw_log)
    if len(kv_tokens) >= 3:
        token_coverage = sum(len(t) for t in kv_tokens) / max(len(raw_log), 1)
        if token_coverage > 0.5:
            return {"format": "KeyValue", "confidence": 0.85, "detector": "keyvalue_detector"}

    return {"format": "UNKNOWN", "confidence": 0.0, "detector": "unknown_detector"}
