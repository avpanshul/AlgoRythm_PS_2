r"""Closes the agentic-onboarding loop's real gap (audit finding: "the loop
isn't closed... an analyst still hand-writes YAML"): given a Drain3 unknown-
format cluster, this drafts a real source-pack YAML automatically by running
each real field the log actually contains through the existing per-field LLM
classifier (app/ai/llm.py, already used for single-field suggestions) and
assembling the results into a real mapping-engine config.

This does NOT auto-activate the pack. The draft is created with
`status="draft"` and `created_by="ai_pack_drafting"`, so it still has to pass
through the exact same human-approval gate every other parser does
(`POST /parsers/{id}/publish`, which already enforces separation of duties
and a real fixture-test pass) -- "no human before ingest" would contradict
this project's own C2 review-gate finding, so this stays agentic-*assisted*,
not autonomous, by design.
"""
from collections import Counter

from sqlalchemy.orm import Session
import yaml

from app.core.config import settings
from app.models.all import DLQEvent, Parser, AgentReasoningTraceEntry
from app.parsers.format_detector import detect_format
from app.parsers.deterministic import parse_log
from app.core.processing import _flatten_dict
# Lazy import (inside draft_pack_for_cluster, not at module level): this
# module is imported by app.main at startup via unknown_clusters.py, and
# app.ai.llm pulls in sentence-transformers (a heavy, optional-at-startup
# dependency) transitively via app.ai.embeddings -- the existing convention
# elsewhere in this codebase (e.g. app/services/mapping_service.py's own
# use of it) is exactly this deferred-import pattern for the same reason.

MIN_CONFIDENCE = 0.5
MAX_SAMPLE_LOGS = 5
MAX_FIELDS_TO_CLASSIFY = 20


def _representative_samples(db: Session, cluster_id: str, limit: int = MAX_SAMPLE_LOGS) -> list:
    # status == "failed": real bug found live -- this had no status filter,
    # so a cluster whose real events were already fixed by a later parser
    # (their DLQEvent rows flipped to "resolved") still looked draftable,
    # pulling stale already-solved samples into a fresh draft attempt for no
    # reason. Only currently-unresolved samples represent real remaining work.
    rows = (
        db.query(DLQEvent.raw_log)
        .filter(DLQEvent.drain_cluster_id == cluster_id, DLQEvent.raw_log.isnot(None), DLQEvent.status == "failed")
        .order_by(DLQEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows]


def classify_sample_fields(sample: str, vendor: str = None, device_type: str = None,
                            only_fields: set = None, fields_feedback: dict = None) -> dict:
    """Real, live detection + per-field LLM classification of a single raw
    sample -- the shared core of `draft_pack_for_cluster`, factored out so it
    can also run against an arbitrary pasted sample (e.g. the Add Source
    wizard) without needing an existing DLQ cluster or writing a Parser row.
    Returns real detector/parser/LLM output every time; never a canned
    illustrative preview.

    Item 5 (agent refine loop): `only_fields`, if given, restricts
    classification to that subset of raw field names (a refine attempt only
    re-asks about fields that were UNKNOWN last time, not everything again).
    `fields_feedback` maps a raw_field to a real feedback string from a
    previous attempt's fixture-test result, passed to the LLM (never to the
    deterministic path -- a table lookup can't use feedback, it either knows
    the name or it doesn't)."""
    detection = detect_format(sample)
    format_type = detection["format"]
    # Real bug found live: format_detector.py actually returns "UNKNOWN"
    # (all caps), not "Unknown" -- this check never matched, so a genuinely
    # undetectable sample never hit the honest early-return below. It fell
    # through into parse_log()/deterministic.py's own UNKNOWN branch
    # ({"raw": raw_log}), which classify_sample_fields would try to treat as
    # real structured fields to classify, producing a garbage empty draft
    # instead of a clear "couldn't detect a format" result.
    if format_type == "UNKNOWN":
        return {"status": "undetectable_format", "detail": "Could not confidently detect a known log format from this sample", "format_type": "UNKNOWN", "format_confidence": detection.get("confidence", 0.0)}

    # Real bug found live: the core CSV parser (deterministic.py:parse_csv)
    # only ever sees ONE line at a time, by design -- real per-event CSV
    # ingestion has no embedded header per row, so it correctly names fields
    # positionally (field_0, field_1, ...). But this wizard preview takes a
    # user-pasted *sample*, which can legitimately include a real header row
    # above a real data row -- and without using it, every field showed as
    # a meaningless field_0/field_1/... with no real name to classify at
    # all. Scoped to just this preview path (never touches the real
    # per-event parser used by actual ingestion) so this doesn't change
    # behavior for any real CSV source's live events.
    if format_type == "CSV":
        lines = [ln for ln in sample.splitlines() if ln.strip()]
        if len(lines) >= 2:
            headers = [h.strip() for h in lines[0].split(",")]
            values = [v.strip() for v in lines[1].split(",")]
            if len(headers) == len(values) and all(headers):
                parsed = dict(zip(headers, values))
            else:
                parsed = parse_log(sample, format_type)
        else:
            parsed = parse_log(sample, format_type)
    else:
        parsed = parse_log(sample, format_type)
    if not isinstance(parsed, dict) or not parsed:
        return {"status": "unparseable", "detail": f"Deterministic {format_type} parser returned no fields", "format_type": format_type, "format_confidence": detection.get("confidence", 0.0)}

    flat = _flatten_dict(parsed)
    candidate_fields = [
        (k, v) for k, v in flat.items()
        if v not in (None, "") and isinstance(v, (str, int, float)) and len(str(v)) < 200
    ][:MAX_FIELDS_TO_CLASSIFY]
    if only_fields is not None:
        candidate_fields = [(k, v) for k, v in candidate_fields if k in only_fields]

    from app.ai.deterministic_mapping import classify_field_deterministic

    field_mappings = []
    classifications = []
    mode_counts = {"deterministic": 0, "llm": 0}
    for raw_field, sample_value in candidate_fields:
        # Deterministic lookup first (Item 1: LLM reliability) -- a
        # table-backed exact match is strictly more reliable than an LLM
        # call that can time out, and costs nothing. Only unrecognized
        # field names fall through to the LLM.
        result = classify_field_deterministic(raw_field, format_type)
        if result is not None:
            mode = "deterministic"
        else:
            from app.ai.llm import llm_reasoner
            feedback = (fields_feedback or {}).get(raw_field)
            result = llm_reasoner.ask_mapping(
                vendor=vendor or "unknown", device_type=device_type or "unknown",
                field_name=raw_field, field_value=str(sample_value),
                context=sample[:300], feedback=feedback,
            )
            mode = "llm"
        mode_counts[mode] += 1
        classifications.append({"raw_field": raw_field, "sample_value": str(sample_value), "mode": mode, **result})
        if result["selected_field"] != "UNKNOWN" and result["confidence"] >= MIN_CONFIDENCE:
            field_mappings.append({"raw_field": raw_field, "canonical_field": result["selected_field"]})

    return {
        "status": "classified",
        "format_type": format_type,
        "format_confidence": detection.get("confidence", 0.0),
        "field_classifications": classifications,
        "field_mappings": field_mappings,
        "mapped_field_count": len(field_mappings),
        "unmapped_field_count": len(candidate_fields) - len(field_mappings),
        "total_fields_seen": len(flat),
        # Item 1: every response states which mode classified each field --
        # never silently implies "the AI did this" when a table lookup did.
        "classification_modes": mode_counts,
    }


def draft_pack_for_cluster(db: Session, cluster_id: str, vendor: str = None) -> dict:
    """Real, live LLM-assisted drafting: pulls real raw samples for this
    cluster from the DLQ, parses one to get its real field set, classifies
    each real field via the LLM, and returns a real, syntactically valid
    source-pack config -- never a placeholder or hand-authored guess."""
    samples = _representative_samples(db, cluster_id)
    if not samples:
        return {"status": "no_samples", "detail": f"No DLQ events found for cluster {cluster_id}"}

    primary_sample = samples[0]
    result = classify_sample_fields(primary_sample, vendor=vendor)
    if result["status"] != "classified":
        return result
    format_type = result["format_type"]
    classifications = result["field_classifications"]
    field_mappings = result["field_mappings"]
    candidate_fields = [(c["raw_field"], c["sample_value"]) for c in classifications]

    # Item 5: agent refine loop. Single-pass (the block above) remains the
    # exact behavior when the flag is off -- this only runs additionally.
    # Bounded by AGENT_REFINE_MAX_ATTEMPTS and stops early the moment an
    # attempt makes no further progress (never burns the full budget just
    # to re-ask the same unanswerable question the same way).
    reasoning_trace = []
    if settings.ENABLE_AGENT_REFINE:
        reasoning_trace.append(AgentReasoningTraceEntry(
            cluster_id=cluster_id, attempt_number=1, feedback_used=None,
            field_classifications=classifications,
            mapped_field_count=result["mapped_field_count"],
            unmapped_field_count=result["unmapped_field_count"],
        ))
        attempt = 1
        prev_unmapped_count = result["unmapped_field_count"]
        while attempt < settings.AGENT_REFINE_MAX_ATTEMPTS:
            still_unknown = {c["raw_field"] for c in classifications if c["selected_field"] == "UNKNOWN"}
            if not still_unknown:
                break  # full coverage already -- nothing left to refine

            # Real feedback: what canonical fields the pipeline still needs,
            # so a refine attempt is a genuinely different question, not the
            # same prompt sent twice.
            from app.ai.embeddings import embedding_engine
            mapped_canonical = {m["canonical_field"] for m in field_mappings}
            still_needed = sorted(set(embedding_engine.canonical_fields) - mapped_canonical)
            feedback_text = (
                f"The previous attempt could not confidently classify this field (returned UNKNOWN). "
                f"This pipeline still has no value for: {', '.join(still_needed[:6]) or 'nothing else -- double check this field specifically'}. "
                f"If this field's real-world meaning matches one of those, choose it; otherwise keep UNKNOWN."
            )
            fields_feedback = {f: feedback_text for f in still_unknown}

            attempt += 1
            refine_result = classify_sample_fields(
                primary_sample, vendor=vendor, only_fields=still_unknown, fields_feedback=fields_feedback,
            )
            if refine_result["status"] != "classified":
                break

            # Merge: replace each refined field's classification/mapping in place.
            refined_by_field = {c["raw_field"]: c for c in refine_result["field_classifications"]}
            classifications = [refined_by_field.get(c["raw_field"], c) for c in classifications]
            field_mappings = [
                {"raw_field": c["raw_field"], "canonical_field": c["selected_field"]}
                for c in classifications
                if c["selected_field"] != "UNKNOWN" and c["confidence"] >= MIN_CONFIDENCE
            ]
            new_unmapped_count = sum(1 for c in classifications if c["selected_field"] == "UNKNOWN")

            reasoning_trace.append(AgentReasoningTraceEntry(
                cluster_id=cluster_id, attempt_number=attempt, feedback_used=feedback_text,
                field_classifications=classifications,
                mapped_field_count=len(field_mappings),
                unmapped_field_count=new_unmapped_count,
            ))

            if new_unmapped_count >= prev_unmapped_count:
                break  # no progress this attempt -- stop rather than burn the rest of the budget
            prev_unmapped_count = new_unmapped_count

        for entry in reasoning_trace:
            db.add(entry)
        # committed together with the Parser row below

    config_json = {
        "field_mappings": field_mappings,
        "static": {"event_data": {"category": "unknown"}},
    }
    config_yaml = yaml.dump(config_json, sort_keys=False)

    pack_id = f"ai-draft-{cluster_id}"
    existing = db.query(Parser).filter(Parser.id == pack_id).first()
    if existing:
        db.delete(existing)
        db.flush()

    parser = Parser(
        id=pack_id,
        name=f"AI-drafted pack for cluster {cluster_id}",
        vendor=vendor,
        device_type=None,
        format_type=format_type,
        version="0.1.0",
        config_yaml=config_yaml,
        config_json=config_json,
        sample_log=primary_sample,
        status="draft",
        coverage_status="ai_drafted",
        created_by="ai_pack_drafting",  # never a real user -- keeps the
        # separation-of-duties check in publish_parser meaningful: any real
        # human approver can publish this, but the AI itself never can.
    )
    db.add(parser)
    db.commit()
    db.refresh(parser)

    from app.api.v1.parsers_api import _run_parser_fixture_test
    fixture_results = [_run_parser_fixture_test(parser, s) for s in samples]
    mapped_counts, unmapped_counts = [], []
    for r in fixture_results:
        ecs = r.get("normalized_ecs") or {}
        if not ecs:
            continue
        unmapped_counts.append(len(ecs.get("unmapped") or {}))
        top_level = [k for k in ("source_ip", "dest_ip", "user_name", "device_vendor", "device_product") if ecs.get(k)]
        event_data_mapped = [k for k, v in (ecs.get("event_data") or {}).items() if v not in (None, "unknown", "info")]
        mapped_counts.append(len(top_level) + len(event_data_mapped))

    return {
        "status": "drafted",
        "parser_id": parser.id,
        "format_type": format_type,
        "samples_tested": len(samples),
        "fixture_results": fixture_results,
        "field_classifications": classifications,
        "mapped_field_count": len(field_mappings),
        "unmapped_field_count": len(candidate_fields) - len(field_mappings),
        "avg_mapped_per_sample": round(sum(mapped_counts) / len(mapped_counts), 1) if mapped_counts else None,
        "avg_unmapped_per_sample": round(sum(unmapped_counts) / len(unmapped_counts), 1) if unmapped_counts else None,
    }
