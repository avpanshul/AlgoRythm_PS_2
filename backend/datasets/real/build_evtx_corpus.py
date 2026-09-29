r"""Builds datasets/real/evtx_corpus.jsonl from evtx_attack_samples/evtx_data.csv.

Provenance: evtx_data.csv is a copy of sbousseaden/EVTX-ATTACK-SAMPLES'
evtx_data.csv (github.com/sbousseaden/EVTX-ATTACK-SAMPLES, MIT licensed) --
a well-known public dataset of real Windows Event Logs captured from actual
attack-technique execution in lab environments (not hand-typed), tagged by
MITRE ATT&CK tactic. 249 distinct EVTX captures, ~9,900 events, spanning
Persistence, Privilege Escalation, Lateral Movement, Credential Access,
Command and Control, Defense Evasion, Discovery, and Execution.

What's real vs. reconstructed: every field VALUE below (Computer, EventID,
ProviderName, SystemTime, and the ~300 sparse EventData columns like
CommandLine/TargetUserName/DestAddress/Hashes) is copied verbatim from the
real CSV. The XML *envelope* around them is reconstructed here, because the
CSV is already a flattened/parsed export -- the original raw EVTX/XML text
itself isn't in this export. This follows the same real-payload/
reconstructed-transport pattern used for the Squid/pfSense vendor packs (see
backend/scripts/seed_vendor_packs.py).
"""
import csv
import json
import os
import sys
from xml.sax.saxutils import escape

DATASET_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(DATASET_DIR, "evtx_attack_samples", "evtx_data.csv")
OUT_PATH = os.path.join(DATASET_DIR, "evtx_corpus.jsonl")

# System-level fields pulled out of the flat CSV row into <System>; everything
# else non-empty becomes an EventData <Data Name="...">.
SYSTEM_FIELDS = {"Channel", "Computer", "EventID", "EventRecordID", "Level",
                 "ProviderName", "SystemTime", "Task", "ThreadID"}
EMPTY_VALUES = {"", "-", None}


def row_to_event_xml(row: dict) -> str:
    system_parts = []
    provider = row.get("ProviderName") or "Microsoft-Windows-Security-Auditing"
    system_parts.append(f'<Provider Name="{escape(provider)}"/>')
    if row.get("EventID") not in EMPTY_VALUES:
        system_parts.append(f'<EventID>{escape(row["EventID"])}</EventID>')
    if row.get("Level") not in EMPTY_VALUES:
        system_parts.append(f'<Level>{escape(row["Level"])}</Level>')
    if row.get("Task") not in EMPTY_VALUES:
        system_parts.append(f'<Task>{escape(row["Task"])}</Task>')
    if row.get("SystemTime") not in EMPTY_VALUES:
        system_parts.append(f'<TimeCreated SystemTime="{escape(row["SystemTime"])}"/>')
    if row.get("Channel") not in EMPTY_VALUES:
        system_parts.append(f'<Channel>{escape(row["Channel"])}</Channel>')
    if row.get("Computer") not in EMPTY_VALUES:
        system_parts.append(f'<Computer>{escape(row["Computer"])}</Computer>')

    data_parts = []
    for key, value in row.items():
        if key in SYSTEM_FIELDS or key in ("EVTX_FileName", "EVTX_Tactic", ""):
            continue
        if value in EMPTY_VALUES:
            continue
        data_parts.append(f'<Data Name="{escape(key)}">{escape(str(value))}</Data>')

    return (
        '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
        f'<System>{"".join(system_parts)}</System>'
        f'<EventData>{"".join(data_parts)}</EventData>'
        '</Event>'
    )


def build():
    if not os.path.exists(CSV_PATH):
        print(f"WARNING: {CSV_PATH} not found -- skipping EVTX corpus build.")
        return

    count = 0
    with open(CSV_PATH, encoding="utf-8", errors="replace") as f_in, \
         open(OUT_PATH, "w", encoding="utf-8") as f_out:
        reader = csv.DictReader(f_in)
        for row in reader:
            raw_xml = row_to_event_xml(row)
            f_out.write(json.dumps({
                "raw": raw_xml,
                "source_id": "WINEVT-ATTACK",
                "mitre_tactic": row.get("EVTX_Tactic"),
                "evtx_file": row.get("EVTX_FileName"),
            }) + "\n")
            count += 1

    print(f"Wrote {count} real Windows Event Log records to {OUT_PATH}")


if __name__ == "__main__":
    build()
