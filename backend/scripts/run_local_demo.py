"""Local demo runner: boots the full FastAPI app against a local SQLite file
instead of Postgres.

Why this exists: this environment has no Docker and no Postgres role/database
matching the project's .env credentials (the Postgres processes running on
this machine belong to something else -- unknown credentials, not touched).
This script lets you see the whole app running end to end without either.
Not for production and not how docker-compose.yml runs it -- just a
convenience so `docker compose up` isn't required to try the UI locally.

Usage: python scripts/run_local_demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("POSTGRES_PASSWORD", "local-demo-unused")
os.environ.setdefault("ADMIN_INITIAL_EMAIL", "admin@ulpf.local")
os.environ.setdefault("ADMIN_INITIAL_PASSWORD", "local-demo-admin-pw")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:3000")
# Real bug found live: this script sets CORS_ORIGINS directly (independent
# of app/core/config.py's own default), so fixing the default there alone
# didn't help -- this hardcoded copy is what the local dev server actually
# used. 5174 added since the frontend dev server landed there (5173 was
# already taken at the time it started).

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.core.database as database  # noqa: E402

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "local_demo.sqlite3")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

database.engine = create_engine(
    f"sqlite:///{DB_PATH}",
    # timeout: how long a writer waits on a lock before raising "database is
    # locked", instead of the default ~5s. Real bug hit live: the 30s
    # live-detection background thread and a replay job's background thread
    # both write to this same SQLite file, and SQLite only allows one writer
    # at a time -- a replay job landed mid-write against a live-detection
    # write and failed outright. WAL mode (below) plus a longer busy timeout
    # is the standard SQLite fix for "one writer, some readers, don't want
    # them to collide" instead of serializing everything through the app.
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(database.engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)

# Import models + create tables directly (skip Alembic, which is wired to the
# Postgres URI in alembic/env.py and would fail against SQLite).
from app.models import all as models  # noqa: E402,F401

database.Base.metadata.create_all(bind=database.engine)
print(f"SQLite demo DB ready at {DB_PATH}")

if __name__ == "__main__":
    import uvicorn

    # Patch out the Alembic migration attempt in main.py's startup event --
    # it targets Postgres and would just print a (harmless but noisy) warning.
    import app.main as main_module

    original_startup = main_module.startup_event

    def patched_startup():
        try:
            from app.core.database import SessionLocal
            from app.core.security import hash_password
            from app.models.all import User, Role
            from app.core.config import settings

            db = SessionLocal()
            try:
                if not db.query(User).filter(User.email == settings.ADMIN_INITIAL_EMAIL).first():
                    if not db.query(Role).filter(Role.name == "admin").first():
                        db.add(Role(name="admin", description="Full administrative access", permissions=["*"]))
                        db.commit()
                    db.add(User(
                        id="admin", name="Administrator", email=settings.ADMIN_INITIAL_EMAIL,
                        role_name="admin", status="active",
                        password_hash=hash_password(settings.ADMIN_INITIAL_PASSWORD),
                    ))
                    db.commit()
                    print(f"Seeded admin user {settings.ADMIN_INITIAL_EMAIL} / {settings.ADMIN_INITIAL_PASSWORD}")
            finally:
                db.close()
        except Exception as e:
            print(f"Admin seed skipped: {e}")

        # patched_startup fully replaces main.py's real startup_event (see
        # this function's own docstring/comment above) rather than calling
        # it, so anything startup_event does -- including starting the
        # auto-ingest scheduler -- has to be repeated here explicitly or it
        # silently never runs under local demo mode. Real gap found and
        # fixed while wiring up app/services/auto_ingest.py.
        try:
            from app.services.auto_ingest import start_auto_ingest
            start_auto_ingest()
        except Exception as e:
            print(f"Auto-ingest scheduler start skipped: {e}")

        try:
            from app.workers.checkpoint_scheduler import start_background_reverification
            start_background_reverification()
        except Exception as e:
            print(f"Checkpoint re-verification scheduler start skipped: {e}")

    main_module.app.router.on_startup.remove(original_startup)
    main_module.app.router.on_startup.append(patched_startup)

    uvicorn.run(main_module.app, host="0.0.0.0", port=8000)
