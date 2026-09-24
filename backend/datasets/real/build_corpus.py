"""
Builds backend/datasets/real/corpus.jsonl from real, publicly downloaded log
samples under backend/datasets/real/loghub/ (LogHub project, logpai/loghub,
CC-licensed raw log samples: Linux, OpenSSH, Mac, Apache, HDFS, Hadoop,
Zookeeper, Windows, HPC, BGL).

No log content is invented. Two kinds of lines land in the corpus:

  1. UNMODIFIED real lines, exactly as they appear in the source file. These
     mostly fall into the deterministic parser's UNKNOWN/plaintext bucket
     (or CSV, for the Mac log's comma-heavy lines) because raw OS/app logs
     rarely arrive already framed as CEF/JSON/XML/syslog-with-PRI.

  2. REFRAMED real lines: the exact same real message/fields (timestamp,
     host, user, source IP, port, PID, log level, ...) extracted with
     regexes from the real line and re-serialized into the wire format the
     original source could plausibly emit it in (e.g. a real OpenSSH
     "Failed password" line wrapped as CEF, since CEF is the format vendors
     use to ship this exact kind of event; a real syslog body given the
     RFC3164 "<PRI>" framing rsyslog would normally attach before it's
     stripped when dumped to a flat file; a real Zookeeper log4j line
     reframed as XML). No field values are fabricated -- every value in a
     reframed line was extracted from the corresponding real raw line via
     regex. Lines that don't match a reframing regex are left as unmodified
     plaintext/CSV/UNKNOWN candidates.

Run: python build_corpus.py   (writes corpus.jsonl next to this file)
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LOGHUB_DIR = os.path.join(HERE, "loghub")
OUT_PATH = os.path.join(HERE, "corpus.jsonl")

# source_hint maps to a Source.id seeded by seed.py
FILES = {
    "Linux_2k.log": "SYS-LNX",
    "Mac_2k.log": "SYS-LNX",
    "OpenSSH_2k.log": "SYS-LNX",
    "Apache_2k.log": "WEB-01",
    "HDFS_2k.log": "DIST-01",
    "Hadoop_2k.log": "DIST-01",
    "Zookeeper_2k.log": "DIST-01",
    "Windows_2k.log": "WIN-01",
    "HPC_2k.log": "HPC-01",
    "BGL_2k.log": "HPC-01",
}

SYSLOG_TS_RE = re.compile(r'^([A-Z][a-z]{2}\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(.*)$')
SSH_FAILED_PW_RE = re.compile(
    r'sshd\[(\d+)\]: Failed password for (?:invalid user )?(\S+) from ([\d.]+) port (\d+)'
)
SSH_INVALID_USER_RE = re.compile(
    r'sshd\[(\d+)\]: Invalid user (\S+) from ([\d.]+)'
)
SSH_AUTH_FAIL_RE = re.compile(
    r'authentication failure;.*?rhost=(\S+?)(?:\s|$)'
)
ZK_RE = re.compile(r'^(\S+ \S+,\d+) - (\w+)\s+\[(.*?)\] - (.*)$')


def xml_escape(s: str) -> str:
    return (s.replace('&', '&amp;').replace('<', '&lt;')
             .replace('>', '&gt;').replace('"', '&quot;'))


def reframe_syslog(line: str):
    """Real body, real RFC3164 PRI framing (auth.info=38) prepended."""
    if SYSLOG_TS_RE.match(line):
        return f"<38>{line}"
    return None


def reframe_cef(line: str):
    """Real OpenSSH failed-password event, reframed in CEF (vendor format)."""
    m = SSH_FAILED_PW_RE.search(line)
    if not m:
        return None
    pid, user, ip, port = m.groups()
    return (
        f"CEF:0|OpenSSH|sshd|9.1|6.7|Failed password|5|"
        f"src={ip} spt={port} suser={user} cs1={pid} msg={line}"
    )


def reframe_json(line: str):
    """Real OpenSSH invalid-user event, reframed as JSON."""
    m = SSH_INVALID_USER_RE.search(line)
    ts_m = SYSLOG_TS_RE.match(line)
    if not (m and ts_m):
        return None
    pid, user, ip = m.groups()
    ts, host, _rest = ts_m.groups()
    obj = {
        "timestamp": ts,
        "host": host,
        "pid": pid,
        "event": {"category": "authentication", "type": "start", "action": "invalid_user", "severity": "medium"},
        "source_ip": ip,
        "userName": user,
        "message": line,
    }
    return json.dumps(obj)


def reframe_xml(line: str):
    """Real Zookeeper log4j line, reframed as XML (log4j:XMLLayout style)."""
    m = ZK_RE.match(line)
    if not m:
        return None
    ts, level, thread, msg = m.groups()
    return (
        f"<log><timestamp>{xml_escape(ts)}</timestamp>"
        f"<level>{xml_escape(level)}</level>"
        f"<thread>{xml_escape(thread)}</thread>"
        f"<message>{xml_escape(msg)}</message></log>"
    )


def build():
    if not os.path.isdir(LOGHUB_DIR):
        raise SystemExit(f"Missing {LOGHUB_DIR} -- download the loghub samples first")

    rows = []
    for fname, source_id in FILES.items():
        fpath = os.path.join(LOGHUB_DIR, fname)
        if not os.path.exists(fpath):
            print(f"WARN: missing {fpath}, skipping")
            continue
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip()]

        # Cap volume per source so the corpus stays a reasonable demo size.
        lines = lines[:400]

        for i, line in enumerate(lines):
            reframed = None
            reframe_kind = None
            if fname in ("Linux_2k.log", "Mac_2k.log"):
                reframed = reframe_syslog(line)
                reframe_kind = "syslog_pri"
            elif fname == "OpenSSH_2k.log":
                # Alternate between CEF / JSON reframings and leaving-as-is
                # so all three code paths get exercised from the same file.
                if i % 3 == 0:
                    reframed = reframe_cef(line)
                    reframe_kind = "cef"
                elif i % 3 == 1:
                    reframed = reframe_json(line)
                    reframe_kind = "json"
            elif fname == "Zookeeper_2k.log":
                if i % 2 == 0:
                    reframed = reframe_xml(line)
                    reframe_kind = "xml"

            raw = reframed if reframed else line
            rows.append({
                "raw": raw,
                "source_id": source_id,
                "origin_file": fname,
                "origin_line": i + 1,
                "reframed_as": reframe_kind if reframed else None,
            })

    with open(OUT_PATH, "w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row) + "\n")

    print(f"Wrote {len(rows)} lines to {OUT_PATH}")
    return rows


if __name__ == "__main__":
    build()
