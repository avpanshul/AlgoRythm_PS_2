r"""Database-portable helpers.

`func.date_trunc(...)` is PostgreSQL-only -- calling it against the dev/test
SQLite backend raises `sqlite3.OperationalError: no such function:
date_trunc`. This was a real, live bug: every endpoint using it
(`/api/v1/stats`'s events-over-time chart, `/api/v1/analytics/timeseries`)
either silently returned an empty result (where wrapped in a bare
`try/except`) or raised a raw 500 (where it wasn't) on the SQLite backend
this project actually runs against in dev -- found running a real sanity
check against the live dashboard, not by reading the code.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

_SQLITE_FORMATS = {
    "minute": "%Y-%m-%dT%H:%M:00",
    "hour": "%Y-%m-%dT%H:00:00",
    "day": "%Y-%m-%dT00:00:00",
}


def date_trunc_expr(db: Session, interval: str, column):
    """Returns a SQLAlchemy expression that buckets `column` by `interval`
    ("minute"/"hour"/"day"), portable across Postgres (real `date_trunc`)
    and SQLite (`strftime`-based bucketing, since SQLite has no native
    truncation function). The SQLite path returns a plain ISO-shaped string
    rather than a datetime -- callers should use `bucket_label` below rather
    than assuming a `.isoformat()`-capable value."""
    dialect = db.bind.dialect.name
    if dialect == "sqlite":
        return func.strftime(_SQLITE_FORMATS[interval], column)
    return func.date_trunc(interval, column)


def bucket_label(value) -> str | None:
    """Normalizes a date_trunc_expr result to an ISO string regardless of
    whether the backend returned a datetime (Postgres) or a string
    (SQLite)."""
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)
