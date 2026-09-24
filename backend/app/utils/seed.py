"""
DEPRECATED. This module used to seed MinIO + OpenSearch with 8 hand-typed
"synthetic" log lines fabricated to look like a firewall-deny + login
sequence. Per the project rule that no sample/synthetic data may ship in
the seed path, that content was removed rather than "fixed" in place.

Use `python seed.py` (backend/seed.py) instead -- it seeds Postgres by
running real, publicly downloaded log lines (backend/datasets/real/) through
the actual app/core/processing.py:process_raw_event() pipeline. If the
MinIO/OpenSearch demo path from this old module is still needed, it should
be rebuilt to source raw lines from backend/datasets/real/ the same way,
rather than restoring the old fabricated SYNTHETIC_LOGS list.
"""
import sys

if __name__ == "__main__":
    print(__doc__)
    sys.exit(1)
