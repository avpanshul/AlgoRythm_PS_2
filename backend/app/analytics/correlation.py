r"""Cross-source, cross-event correlation engine (ULPF-phase2-prompt.md E1).

Sits downstream of normalized events -- reads NormalizedEvent rows already
written by app/core/processing.py, never reparses raw logs. Rules are data
(YAML in app/analytics/correlation_rules/), not code, per E1's explicit
requirement, so a new attack pattern is a new YAML file, not a new deploy.

Each rule defines an ordered sequence of "stages" (e.g. brute_force then
lateral_movement), a grouping key events are correlated by (typically
source_ip), a sliding time window, and a minimum number of *distinct log
sources* that must contribute matching events -- this last part is what
makes it cross-source-type correlation rather than a same-source rule
filtering, per E1's explicit requirement not to scope correlation to one
source type.

A match creates one CorrelatedIncident row (id doubles as the
`correlation_id` stamped onto every matched NormalizedEvent) and is
idempotent per (rule_id, correlate_key, window) -- re-running evaluation
doesn't create duplicate incidents for the same underlying event set.
"""
import glob
import os
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import yaml
from sqlalchemy.orm import Session

from app.models.all import NormalizedEvent, CorrelatedIncident, CorrelationRule

RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "correlation_rules")


def load_rules() -> list:
    rules = []
    for path in sorted(glob.glob(os.path.join(RULES_DIR, "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            rules.append(yaml.safe_load(f))
    return rules


def _matches_stage(event: NormalizedEvent, match: dict) -> bool:
    if match.get("any_event"):
        return True

    action = (event.action or "").lower()
    severity = (event.severity or "").lower()

    action_contains = match.get("action_contains")
    if action_contains and not any(kw in action for kw in action_contains):
        return False

    severity_in = match.get("severity_in")
    if severity_in and severity not in severity_in:
        return False

    return bool(action_contains or severity_in or match.get("any_event"))


def _group_key(event: NormalizedEvent, correlate_by: str):
    return getattr(event, correlate_by, None)


def evaluate_rule(db: Session, rule: dict, now: datetime = None) -> list:
    """Evaluates one rule against currently-stored NormalizedEvent rows.

    Looks for a qualifying window *anywhere* in each correlate_by group's own
    event history via a sliding window over that group's own timestamps --
    not a trailing window ending at wall-clock "now". This matters because
    this pipeline's events carry their own real historical timestamps (see
    `normalization.timestamp_source` in app/core/processing.py) rather than
    ingestion time; a rule anchored to wall-clock "now" would only ever see
    events ingested in roughly the last `window_minutes`, silently ignoring
    the vast majority of real historical data. `now` is accepted but no
    longer used for filtering -- kept so existing callers/tests that pass it
    keep working; a live deployment would instead track "last evaluated up
    to event timestamp X" for incremental runs, not implemented yet.

    Returns the list of newly-created CorrelatedIncident objects (already
    added to `db`, not yet committed -- caller commits)."""
    window = timedelta(minutes=rule["window_minutes"])
    correlate_by = rule["correlate_by"]
    min_distinct_sources = rule.get("min_distinct_sources", 1)

    events = (
        db.query(NormalizedEvent)
        .filter(getattr(NormalizedEvent, correlate_by).isnot(None))
        .order_by(NormalizedEvent.timestamp.asc())
        .all()
    )

    groups = defaultdict(list)
    for e in events:
        groups[_group_key(e, correlate_by)].append(e)

    new_incidents = []
    for key, group_events in groups.items():
        group_events.sort(key=lambda e: e.timestamp)

        # Real bug found live: this used to create one CorrelatedIncident
        # PER sliding-window position, so a single sustained burst (e.g. a
        # continuous 829-event password-spray) produced ~829 near-duplicate
        # incidents -- one per event added to the window, event_count
        # incrementing by one each time -- instead of one incident for the
        # whole burst. First fix: merge a contiguous run of qualifying
        # window positions into one "episode" (broken only when a position
        # stops qualifying), and emit one incident per episode using the
        # union of its matched events.
        episodes: list[dict] = []
        current_episode = None
        left = 0
        for right in range(len(group_events)):
            while group_events[right].timestamp - group_events[left].timestamp > window:
                left += 1
            window_events = group_events[left:right + 1]
            if len(window_events) < 2:
                current_episode = None
                continue

            stage_matches = {}
            for stage in rule["stages"]:
                matched = [e for e in window_events if _matches_stage(e, stage["match"])]
                if "min_distinct_dest_ports" in stage:
                    distinct_ports = {e.dest_port for e in window_events if e.dest_port is not None}
                    if len(distinct_ports) < stage["min_distinct_dest_ports"]:
                        matched = []
                if "min_distinct_user_names" in stage:
                    # Password-spraying shape: many distinct *target* accounts
                    # attempted from the same real-world actor in a short
                    # window -- the actor identity itself often isn't
                    # available in the log (e.g. real Windows NTLM Event ID
                    # 8004 records the target account, not a source IP), so
                    # this generalizes min_distinct_dest_ports's pattern to
                    # user_name instead of assuming a network 5-tuple exists.
                    distinct_users = {e.user_name for e in window_events if e.user_name}
                    if len(distinct_users) < stage["min_distinct_user_names"]:
                        matched = []
                stage_matches[stage["name"]] = matched

            if not _stages_satisfied(rule["stages"], stage_matches):
                current_episode = None
                continue

            matched_events = {e for evs in stage_matches.values() for e in evs}
            distinct_sources = {e.source_id for e in matched_events if e.source_id}
            if len(distinct_sources) < min_distinct_sources:
                current_episode = None
                continue

            if current_episode is None:
                current_episode = {"events": set()}
                episodes.append(current_episode)
            current_episode["events"].update(matched_events)

        for episode in episodes:
            matched_events = episode["events"]
            distinct_sources = {e.source_id for e in matched_events if e.source_id}
            event_ids = sorted(e.event_id for e in matched_events)
            timestamps = [e.timestamp for e in matched_events]
            first_at, last_at = min(timestamps), max(timestamps)
            stage_summary = {
                stage["name"]: len([e for e in matched_events if _matches_stage(e, stage["match"])])
                for stage in rule["stages"]
            }

            # Second fix, for idempotency *across* evaluation runs (the
            # live-detection loop calls evaluate_rule() every 30s): if an
            # open incident for this same rule+key already covers an
            # overlapping/adjacent time range, extend it in place -- add any
            # newly-seen events, recompute distinct_source_count/
            # stage_summary over the full merged set, bump last_event_at --
            # instead of minting a fresh row each cycle. This is what keeps
            # one ongoing attack as ONE incident over time, matching this
            # module's own documented idempotency claim.
            existing = (
                db.query(CorrelatedIncident)
                .filter(
                    CorrelatedIncident.rule_id == rule["id"],
                    CorrelatedIncident.correlate_key == str(key),
                    CorrelatedIncident.status == "open",
                    CorrelatedIncident.last_event_at >= first_at - window,
                    CorrelatedIncident.first_event_at <= last_at + window,
                )
                .order_by(CorrelatedIncident.last_event_at.desc())
                .first()
            )

            if existing:
                merged_ids = sorted(set(existing.event_ids or []) | set(event_ids))
                if merged_ids == sorted(existing.event_ids or []):
                    continue  # nothing new since the last evaluation cycle
                merged_events = (
                    db.query(NormalizedEvent)
                    .filter(NormalizedEvent.event_id.in_(merged_ids))
                    .all()
                )
                existing.event_ids = merged_ids
                existing.distinct_source_count = len({e.source_id for e in merged_events if e.source_id})
                existing.stage_summary = {
                    stage["name"]: len([e for e in merged_events if _matches_stage(e, stage["match"])])
                    for stage in rule["stages"]
                }
                existing.first_event_at = min(first_at, existing.first_event_at)
                existing.last_event_at = max(last_at, existing.last_event_at)
                for e in merged_events:
                    if not e.correlation_id:
                        e.correlation_id = existing.id
                continue

            incident_key = f"{rule['id']}:{key}:{first_at.isoformat()}"
            dedupe_id = "corr-" + uuid.uuid5(uuid.NAMESPACE_URL, incident_key).hex[:24]
            if db.query(CorrelatedIncident).filter(CorrelatedIncident.id == dedupe_id).first():
                continue  # already recorded an incident starting at this exact moment

            incident = CorrelatedIncident(
                id=dedupe_id,
                rule_id=rule["id"],
                rule_name=rule["name"],
                correlate_key=str(key),
                event_ids=event_ids,
                distinct_source_count=len(distinct_sources),
                stage_summary=stage_summary,
                first_event_at=first_at,
                last_event_at=last_at,
            )
            db.add(incident)
            new_incidents.append(incident)

            for e in matched_events:
                if not e.correlation_id:
                    e.correlation_id = dedupe_id

    _bump_rule_bookkeeping(db, rule, len(new_incidents))
    return new_incidents


def _stages_satisfied(stage_defs: list, stage_matches: dict) -> bool:
    for stage in stage_defs:
        matched = stage_matches.get(stage["name"], [])
        if len(matched) < stage.get("min_count", 1):
            return False
        after = stage.get("after")
        if after:
            prior_matched = stage_matches.get(after, [])
            if not prior_matched:
                return False
            # The "after" ordering requirement: at least one match in this
            # stage must occur strictly after the earliest match of the
            # stage it depends on -- proves a sequence, not just co-occurrence.
            earliest_prior = min(e.timestamp for e in prior_matched)
            if not any(e.timestamp > earliest_prior for e in matched):
                return False
    return True


def _bump_rule_bookkeeping(db: Session, rule: dict, new_match_count: int):
    """Keeps the existing CorrelationRule table (seed.py's simple
    threshold-rule rows) as the bookkeeping/visibility record for these
    richer YAML rules too -- one place to see matches_24h/last_matched_at
    for any rule, old shape or new."""
    if new_match_count <= 0:
        return
    row = db.query(CorrelationRule).filter(CorrelationRule.name == rule["name"]).first()
    if not row:
        row = CorrelationRule(
            name=rule["name"], description=rule.get("description"), severity="high",
            enabled=True, condition={"engine": "correlation.py", "rule_id": rule["id"]},
        )
        db.add(row)
        db.flush()
    row.matches_24h = (row.matches_24h or 0) + new_match_count
    row.last_matched_at = datetime.now(timezone.utc)


def evaluate_all_rules(db: Session) -> dict:
    summary = {}
    for rule in load_rules():
        incidents = evaluate_rule(db, rule)
        summary[rule["id"]] = len(incidents)
    db.commit()
    return summary
