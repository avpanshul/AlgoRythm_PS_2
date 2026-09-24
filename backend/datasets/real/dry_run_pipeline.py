"""
DB-free smoke test: runs every line in corpus.jsonl through the real
detect_format -> parse_log -> normalize_parsed_data -> redact_pii ->
compute_risk_score chain (the same functions app/core/processing.py:
process_raw_event uses) and reports pass/fail counts, a format breakdown,
and any exceptions raised by real data.

Use this when no Postgres instance is reachable -- it exercises the actual
parsing/normalization/risk code, just without the DB write at the end.

Run: python dry_run_pipeline.py
"""
import json
import os
import sys
import traceback
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.parsers.format_detector import detect_format
from app.parsers.deterministic import parse_log
from app.core.processing import normalize_parsed_data, redact_pii, compute_risk_score

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_PATH = os.path.join(HERE, "corpus.jsonl")


def main():
    if not os.path.exists(CORPUS_PATH):
        raise SystemExit(f"{CORPUS_PATH} not found -- run build_corpus.py first")

    format_counts = Counter()
    dlq_reason_counts = Counter()
    ok = 0
    dlq = 0
    exceptions = []
    risk_scores = []
    quality_scores = []

    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    for row in rows:
        raw_log = row["raw"]
        try:
            detection = detect_format(raw_log)
            fmt = detection["format"]
            format_counts[fmt] += 1

            if fmt == "UNKNOWN":
                dlq += 1
                dlq_reason_counts["UNKNOWN format"] += 1
                continue

            parsed = parse_log(raw_log, fmt)
            if not parsed or parsed == {} or (isinstance(parsed, dict) and parsed.get("raw") == raw_log):
                dlq += 1
                dlq_reason_counts[f"empty parse ({fmt})"] += 1
                continue

            normalized = normalize_parsed_data(parsed, fmt, raw_log)
            redacted_message, redacted_fields = redact_pii(normalized.get("message") or "")
            normalized["message"] = redacted_message
            risk_score, risk_level = compute_risk_score(normalized["event_data"], normalized.get("source_ip"))

            filled = sum(1 for v in [
                normalized["source_ip"], normalized["dest_ip"],
                normalized["event_data"].get("action"), normalized["event_data"].get("severity"),
                normalized["message"], normalized.get("user_name"),
                normalized.get("network_protocol")
            ] if v and v != "unknown")
            quality_score = min(100, int(filled / 7 * 100))

            risk_scores.append(risk_score)
            quality_scores.append(quality_score)
            ok += 1
        except Exception as e:
            exceptions.append({
                "origin_file": row.get("origin_file"),
                "origin_line": row.get("origin_line"),
                "raw": raw_log[:200],
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(limit=3),
            })

    print(f"Total lines: {len(rows)}")
    print(f"  Parsed OK -> would become NormalizedEvent: {ok}")
    print(f"  Would go to DLQ (UNKNOWN/empty parse): {dlq}")
    print(f"  Raised an exception (parser bug): {len(exceptions)}")
    print()
    print("Format detection breakdown (all lines):")
    for fmt, n in format_counts.most_common():
        print(f"  {fmt}: {n}")
    print()
    print("DLQ reason breakdown:")
    for reason, n in dlq_reason_counts.most_common():
        print(f"  {reason}: {n}")
    if risk_scores:
        print()
        print(f"Risk score range on successfully parsed events: min={min(risk_scores)} max={max(risk_scores)} avg={sum(risk_scores)/len(risk_scores):.1f}")
        print(f"Quality score range: min={min(quality_scores)} max={max(quality_scores)} avg={sum(quality_scores)/len(quality_scores):.1f}")
    if exceptions:
        print()
        print(f"=== {len(exceptions)} EXCEPTIONS (first 10) ===")
        for exc in exceptions[:10]:
            print(f"[{exc['origin_file']}:{exc['origin_line']}] {exc['error']}")
            print(f"  raw: {exc['raw']}")


if __name__ == "__main__":
    main()
