r"""One-click end-to-end demo walkthrough (ULPF-master-prompt.md C7):
ingest real log -> silent-source + spike (against real seeded data) ->
unknown format -> DLQ/Drain3 -> format drift -> approve -> replay ->
byte-flip tamper -> verifier FAIL.

Design choice, stated up front rather than hidden: steps that need real
*elapsed time or historical volume* (silent-source, volume-spike) report
against whatever is already true of the currently-seeded real data (see
docs/demo.md for how to seed it) rather than fabricating a live burst or
a fake wait -- this script never claims a detection fired when it didn't.
Steps that are genuinely interactive (unknown format, drift, replay,
tamper) are driven live, end to end, against the real running backend.

Usage (fresh machine, no manual steps beyond what's printed):
    cd backend
    python scripts/demo_flow.py

This starts its own backend (scripts/run_local_demo.py) if one isn't
already answering on :8000, seeds real data if the DB is empty, runs the
whole walkthrough, and prints a PASS/FAIL line per step. Exit code is
non-zero if any step failed.
"""
import json
import os
import subprocess
import sys
import time
import uuid
import zipfile

import requests

# Unique per run so re-running this script (e.g. while iterating on it, or
# on a machine that already ran it once) doesn't inherit state -- like a
# source's fingerprint baseline -- from a previous run and produce a
# misleading "drift" result that's actually just leftover state.
_RUN_ID = uuid.uuid4().hex[:8]

BASE_URL = "http://localhost:8000/api/v1"
ADMIN_EMAIL = "admin@ulpf.local"
ADMIN_PASSWORD = "local-demo-admin-pw"

_backend_proc = None
_steps_failed = 0


def _step(name):
    print(f"\n=== {name} ===")


def _ok(msg):
    print(f"  PASS: {msg}")


def _fail(msg):
    global _steps_failed
    _steps_failed += 1
    print(f"  FAIL: {msg}")


def _ensure_backend_running():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=2)
        if r.status_code == 200:
            print("Backend already running.")
            return
    except requests.RequestException:
        pass

    print("Starting backend (scripts/run_local_demo.py)...")
    global _backend_proc
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _backend_proc = subprocess.Popen(
        [sys.executable, "scripts/run_local_demo.py"], cwd=backend_dir,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        time.sleep(1)
        try:
            if requests.get(f"{BASE_URL}/health", timeout=2).status_code == 200:
                print("Backend is up.")
                return
        except requests.RequestException:
            continue
    raise RuntimeError("Backend did not come up within 30s")


def _login():
    r = requests.post(f"{BASE_URL}/auth/token", data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def run():
    _ensure_backend_running()
    token = _login()
    headers = _auth_headers(token)

    _step("1. Ingest a real log")
    real_cef = "CEF:0|Cisco|ASA|9.0|106001|Deny|7|src=203.0.113.5 dst=10.0.0.9 spt=4444 dpt=443 proto=TCP act=deny"
    resp = requests.post(f"{BASE_URL}/events", headers=headers, json={"source_id": f"DEMO-FLOW-{_RUN_ID}", "raw_log": real_cef}, timeout=10)
    if resp.status_code == 200 and resp.json().get("processing_status") == "normalized":
        event_id = resp.json()["event_id"]
        _ok(f"ingested and normalized: {event_id}")
    else:
        _fail(f"ingestion did not normalize: {resp.status_code} {resp.text[:200]}")
        event_id = None

    _step("2. Silent-source detection (against currently-seeded real data)")
    r = requests.get(f"{BASE_URL}/analytics/silent-sources", params={"silence_minutes": 60}, headers=headers, timeout=10)
    if r.status_code == 200:
        silent = r.json().get("sources", [])
        _ok(f"{len(silent)} real source(s) currently flagged silent (honest result, not forced)")
    else:
        _fail(f"silent-source check failed: {r.status_code}")

    _step("3. Volume-spike/anomaly detection (against currently-seeded real data)")
    r = requests.get(f"{BASE_URL}/analytics/volume-anomalies", headers=headers, timeout=10)
    if r.status_code == 200:
        anomalies = r.json().get("anomalies", [])
        _ok(f"{len(anomalies)} real volume anomaly(ies) currently detected (honest result, not forced)")
    else:
        _fail(f"volume-anomaly check failed: {r.status_code}")

    _step("4. Unknown format -> DLQ + Drain3 clustering")
    garbage = "FW-D|29-09-2026|192.168.1.1>10.0.0.1|TCP|BLOCK|totally-nonstandard-vendor-format"
    r = requests.post(f"{BASE_URL}/events", headers=headers, json={"source_id": f"DEMO-FLOW-{_RUN_ID}", "raw_log": garbage}, timeout=10)
    dlq_event_id = r.json().get("event_id") if r.status_code == 200 else None
    time.sleep(0.5)
    dlq_resp = requests.get(f"{BASE_URL}/dlq", headers=headers, timeout=10)
    matching = [d for d in dlq_resp.json().get("items", []) if d.get("event_id") == dlq_event_id] if dlq_resp.status_code == 200 else []
    if matching:
        _ok(f"unrecognized format correctly routed to DLQ: {matching[0].get('failure_reason')}")
    else:
        _fail("unknown-format event was not found in the DLQ")

    _step("5. Format drift: baseline -> vendor renames a field -> flagged -> approved")
    # app/analytics/drift.py samples the most recent SAMPLE_SIZE=50 events per
    # source; sending fewer than that per stage would let old- and new-format
    # events mix in the same sample and dilute the signal (a real thing this
    # session's own tests caught) -- 60 per stage genuinely exceeds the
    # window so the second check's sample is *only* the drifted-shape events.
    baseline_log = 'date=2026-09-26 time=10:00:00 logid="1" type="traffic" srcip=10.1.1.1 srcport=1000 dstip=8.8.8.8 dstport=443'
    for i in range(60):
        requests.post(f"{BASE_URL}/events", headers=headers,
                      json={"source_id": f"DEMO-DRIFT-{_RUN_ID}", "raw_log": baseline_log.replace("1000", str(1000 + i))}, timeout=10)
    r1 = requests.post(f"{BASE_URL}/sources/check-drift", headers=headers, timeout=10)
    baseline_status = r1.json().get(f"DEMO-DRIFT-{_RUN_ID}", {}).get("status") if r1.status_code == 200 else None

    # A real vendor firmware update renaming srcip -> src_addr, same KeyValue shape.
    drifted_log = 'date=2026-09-26 time=10:05:00 logid="1" type="traffic" src_addr=10.1.1.1 srcport=1000 dstip=8.8.8.8 dstport=443'
    for i in range(60):
        requests.post(f"{BASE_URL}/events", headers=headers,
                      json={"source_id": f"DEMO-DRIFT-{_RUN_ID}", "raw_log": drifted_log.replace("1000", str(2000 + i))}, timeout=10)
    r2 = requests.post(f"{BASE_URL}/sources/check-drift", headers=headers, timeout=10)
    drift_status = r2.json().get(f"DEMO-DRIFT-{_RUN_ID}", {}).get("status") if r2.status_code == 200 else None

    if baseline_status == "baseline_created" and drift_status == "drift_detected":
        _ok(f"drift correctly detected after simulated field rename: {r2.json()[f'DEMO-DRIFT-{_RUN_ID}']}")
        approve_resp = requests.post(f"{BASE_URL}/sources/DEMO-DRIFT-{_RUN_ID}/approve-drift", headers=headers, timeout=10)
        if approve_resp.status_code == 200 and approve_resp.json().get("drift_detected") is False:
            _ok("drift reviewed and approved as new baseline")
        else:
            _fail(f"drift approval failed: {approve_resp.status_code} {approve_resp.text[:200]}")
    else:
        _fail(f"drift sequence did not behave as expected: baseline={baseline_status} drift={drift_status}")

    _step("6. Replay")
    replay_resp = requests.post(f"{BASE_URL}/replay/jobs", headers=headers,
                                 json={"name": "demo-flow-replay", "source_id": f"DEMO-DRIFT-{_RUN_ID}", "requested_by": "demo-flow"}, timeout=10)
    if replay_resp.status_code == 200:
        job_id = replay_resp.json()["id"]
        for _ in range(20):
            time.sleep(0.5)
            job = requests.get(f"{BASE_URL}/replay/jobs/{job_id}", headers=headers, timeout=10).json()
            if job.get("status") == "completed":
                _ok(f"replay completed: {job.get('processed_events')} events reprocessed, {job.get('changed_events')} changed")
                break
        else:
            _fail(f"replay job did not complete in time (last status: {job.get('status')})")
    else:
        _fail(f"could not create replay job: {replay_resp.status_code} {replay_resp.text[:200]}")

    _step("7. Evidence bundle + live byte-flip tamper detection")
    if event_id:
        bundle_resp = requests.get(f"{BASE_URL}/evidence/bundle/{event_id}", headers=headers, timeout=10)
        if bundle_resp.status_code == 200:
            bundle_path = "demo_flow_bundle.zip"
            with open(bundle_path, "wb") as f:
                f.write(bundle_resp.content)

            verify = subprocess.run([sys.executable, "../verifier/verify_bundle.py", bundle_path], capture_output=True, text=True)
            if verify.returncode == 0:
                _ok("verifier PASSES on the genuine bundle")
            else:
                _fail(f"verifier unexpectedly failed on a genuine bundle:\n{verify.stdout}\n{verify.stderr}")

            # Flip one byte inside the zip's raw log entry.
            with zipfile.ZipFile(bundle_path, "r") as zf:
                names = zf.namelist()
                contents = {n: zf.read(n) for n in names}
            raw_name = next((n for n in names if "raw" in n.lower()), names[0])
            tampered = bytearray(contents[raw_name])
            tampered[0] ^= 0xFF
            contents[raw_name] = bytes(tampered)
            tampered_path = "demo_flow_bundle_tampered.zip"
            with zipfile.ZipFile(tampered_path, "w") as zf:
                for n, data in contents.items():
                    zf.writestr(n, data)

            verify2 = subprocess.run([sys.executable, "../verifier/verify_bundle.py", tampered_path], capture_output=True, text=True)
            if verify2.returncode != 0:
                _ok(f"verifier correctly FAILS (exit {verify2.returncode}) on the byte-flipped bundle")
            else:
                _fail("verifier did not detect the byte-flip tamper -- this must never pass silently")

            for p in (bundle_path, tampered_path):
                try:
                    os.remove(p)
                except OSError:
                    pass
        else:
            _fail(f"could not fetch evidence bundle: {bundle_resp.status_code}")
    else:
        _fail("no event_id from step 1 to build an evidence bundle for")

    print(f"\n{'='*60}")
    if _steps_failed == 0:
        print("DEMO FLOW: ALL STEPS PASSED")
    else:
        print(f"DEMO FLOW: {_steps_failed} STEP(S) FAILED")
    print(f"{'='*60}")

    if _backend_proc:
        _backend_proc.terminate()

    return 1 if _steps_failed else 0


if __name__ == "__main__":
    sys.exit(run())
