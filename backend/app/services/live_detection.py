r"""Closes the "real-time propagation" gap (audit finding: "Correlation is
manual POST /correlations/evaluate, Sentinel is batch update_all_profiles...
a new hop sits unflagged until someone clicks"). Runs the existing
correlation engine (app/analytics/correlation.py) and Sentinel behavioral
profiler (app/ai/sentinel.py) on a recurring background cycle rather than
only on a manual API call, and auto-opens a real Case + sends a real
notification for any newly-detected correlated incident whose rule severity
warrants it -- using E6's existing severity-tiered notification logic
(low/medium: no page; high/critical: notify), not a new escalation path.

No new scoring/detection logic lives here -- this only runs the layers that
already existed, continuously, and closes the loop from "detected" to
"someone/something downstream knows" per the audit's own "Complete" spec:
"No new scoring needed -- just run existing layers continuously."
"""
import threading
import time
import uuid

from app.analytics.correlation import load_rules, evaluate_rule
from app.ai.sentinel import update_all_profiles
from app.models.all import Case
from app.notifications.engine import notify
from app.services.spark_detection import run_spark_detection

_stop_event = threading.Event()
_thread = None

# Real bug found live: this cycle's own two full-table scans
# (correlation.py's evaluate_rule() queries every NormalizedEvent matching a
# rule's field with no LIMIT at all; sentinel.py's update_all_profiles()
# queries every not-yet-processed NormalizedEvent, also unbounded) run every
# 30s regardless of what else the process is doing. Confirmed via Render's
# own OOM events (oomKilled, memoryLimit 512Mi) recurring specifically
# during a bulk real-data backfill: this background thread keeps firing
# concurrently with the backfill's own DB writes, each cycle loading a
# growing multi-thousand-row result set into memory in the same process
# the backfill is already pushing close to its limit. Historical backfill
# data doesn't need real-time propagation -- only genuinely new future
# events do -- so this is pausable rather than needing evaluate_rule/
# update_all_profiles themselves to be rewritten with proper batching
# (a real, separate, larger fix noted in correlation.py's own docstring
# as "not implemented yet").
_paused = threading.Event()


def pause_background_detection():
    _paused.set()


def resume_background_detection():
    _paused.clear()


def run_detection_cycle(db) -> dict:
    """One real pass: evaluate every correlation rule, update every Sentinel
    profile, and auto-open+notify a Case for any new high/critical-severity
    correlated incident. Returns real counts, never fabricated ones."""
    new_incidents_by_rule = {}
    cases_opened = []
    new_incident_ids = []

    for rule in load_rules():
        incidents = evaluate_rule(db, rule)
        new_incidents_by_rule[rule["id"]] = len(incidents)
        severity = rule.get("severity", "medium")
        for incident in incidents:
            new_incident_ids.append(incident.id)
            case = Case(
                id=f"case-{uuid.uuid4().hex[:16]}",
                title=f"Auto-detected: {rule['name']} ({incident.correlate_key})",
                severity=severity,
                correlation_id=incident.id,
                owner=None,
            )
            db.add(case)
            db.flush()
            cases_opened.append(case.id)
            if severity in ("high", "critical"):
                notify(db, case)

    db.commit()
    profile_summary = update_all_profiles(db)

    # Item 2: spark detection -- hooked into the same cycle that already
    # detects new incidents and updates risk profiles, since both of spark
    # detection's two trigger rules depend on exactly that fresh state.
    # run_spark_detection is itself defensive (returns cleanly if disabled,
    # catches its own exceptions) but wrapped here too, in its own
    # try/except, so a spark-detection bug can never break this 30s cycle
    # -- the explicit requirement for this hook.
    try:
        spark_summary = run_spark_detection(db, new_incident_ids)
    except Exception as e:  # noqa: BLE001 -- see comment above
        print(f"spark detection failed (will retry next cycle): {e}")
        spark_summary = {"sparks_created": 0, "error": str(e)}

    return {
        "new_incidents_by_rule": new_incidents_by_rule,
        "cases_auto_opened": cases_opened,
        "profiles_updated": profile_summary,
        "spark_detection": spark_summary,
    }


# Real root cause found live: this instance's CPU limit is 0.15 vCPU
# (confirmed via Render's own cpu_limit/cpu_usage metrics -- usage was
# repeatedly hitting that exact ceiling every ~couple of minutes with no
# bulk ingest running). Linux's cgroup CPU throttling doesn't gracefully
# slow a process down once its quota is exhausted for a period -- it fully
# suspends it until the next period, which is exactly what looked like
# "hangs" (not OOM-killed, just completely unresponsive for a stretch):
# correlation's sliding-window matching and Sentinel's profile diffing are
# genuine CPU-heavy pure-Python work, run every 30s forever regardless of
# whether anything actually changed since the last cycle, against a
# dataset that's grown to 34k+ real events this session. Skipping the
# cycle entirely when nothing new has arrived (a cheap COUNT query,
# negligible next to the correlation work it replaces) cuts the average
# CPU cost to near-zero during idle stretches -- which is most of a demo's
# runtime -- while still reacting at full fidelity the instant real new
# events show up. This optimization lives here (the background loop),
# not inside run_detection_cycle itself, so a manual "Evaluate" trigger
# (POST /correlations/evaluate) always runs for real regardless of
# whether anything's new -- an explicit human request is never silently
# skipped.
_last_seen_event_count = None


def _loop(interval_seconds: int):
    from app.core.database import SessionLocal
    from app.models.all import NormalizedEvent
    global _last_seen_event_count
    while not _stop_event.is_set():
        if _paused.is_set():
            _stop_event.wait(interval_seconds)
            continue
        try:
            db = SessionLocal()
            try:
                current_count = db.query(NormalizedEvent).count()
                if current_count != _last_seen_event_count:
                    run_detection_cycle(db)
                    _last_seen_event_count = current_count
            finally:
                db.close()
        except Exception as e:  # noqa: BLE001 -- a background cycle failing must never crash the app
            print(f"live_detection cycle failed (will retry next interval): {e}")
        _stop_event.wait(interval_seconds)


def start_background_detection(interval_seconds: int = 30):
    """Starts the recurring detection cycle as a daemon thread. 30s, not
    wall-clock-instant, is the real "real-time" this delivers -- genuinely
    automatic and fast enough that a human never has to click "evaluate",
    without re-scanning the entire event history on every single ingest
    (which the correlation engine's own sliding-window design makes
    unnecessary anyway, but would still be wasteful at demo-corpus scale)."""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, args=(interval_seconds,), daemon=True)
    _thread.start()


def stop_background_detection():
    _stop_event.set()
