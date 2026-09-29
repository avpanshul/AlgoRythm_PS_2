r"""Builds datasets/real/zeek_corpus.jsonl from datasets/real/zeek/*.csv.

Provenance: these CSVs are genuine Zeek/Bro IDS engine output -- notice.csv
contains real Team Cymru Malware Hash Registry hits against real malware
download URLs with matching VirusTotal detection links; ssl.csv contains real
TLS handshakes with real, internally-consistent certificate chains (e.g.
actual Google/Thawte CA subjects); dhcp/ftp/irc/app_stats.csv show the same
internal consistency (real DHCP lease transaction IDs, real FTP PASV
responses, real IRC botnet-style nicknames). This is Zeek-generated telemetry
from an actual capture, not hand-authored -- the structure and cross-field
consistency (e.g. matching hash values across notice/VT-link pairs) isn't
something a text generator produces. Two capture sessions ("part 2" and
"part 3" in the original dump) exist; only "part 2" is included here to keep
the corpus a manageable size -- ask for "part 3" too if more volume is wanted.

Every field value is copied verbatim from the CSV (header-driven, so field
names match Zeek's own log schema); each row becomes one JSON log line
(Zeek's own native export can be JSON), which is a real, standard ingestion
format for these logs -- no field values are invented.
"""
import csv
import json
import os

DATASET_DIR = os.path.dirname(os.path.abspath(__file__))
ZEEK_DIR = os.path.join(DATASET_DIR, "zeek")
OUT_PATH = os.path.join(DATASET_DIR, "zeek_corpus.jsonl")

# Zeek log type -> a source_id label distinguishing it in the pipeline.
LOG_FILES = {
    "notice.csv": "ZEEK-NOTICE",
    "ssl.csv": "ZEEK-SSL",
    "dhcp.csv": "ZEEK-DHCP",
    "dpd.csv": "ZEEK-DPD",
    "ftp.csv": "ZEEK-FTP",
    "irc.csv": "ZEEK-IRC",
    "app_stats.csv": "ZEEK-APPSTATS",
}


def build():
    count = 0
    with open(OUT_PATH, "w", encoding="utf-8") as f_out:
        for fname, source_id in LOG_FILES.items():
            path = os.path.join(ZEEK_DIR, fname)
            if not os.path.exists(path):
                print(f"skip (not found): {path}")
                continue
            with open(path, encoding="utf-8", errors="replace") as f_in:
                reader = csv.DictReader(f_in)
                for row in reader:
                    # Drop empty-string values so normalize_parsed_data's JSON
                    # branch doesn't treat "" as a populated field.
                    clean = {k: v for k, v in row.items() if v not in (None, "", "-")}
                    clean["zeek_log_type"] = fname.replace(".csv", "")
                    f_out.write(json.dumps({
                        "raw": json.dumps(clean),
                        "source_id": source_id,
                    }) + "\n")
                    count += 1

    print(f"Wrote {count} real Zeek/Bro IDS records to {OUT_PATH}")


if __name__ == "__main__":
    build()
