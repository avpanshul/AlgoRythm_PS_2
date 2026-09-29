"""One-off: apply the fortigate_traffic_kv mapping fix and add the new
nginx_plus_kv pack to an already-seeded local DB (seed_vendor_packs.py's own
upsert only inserts packs that don't exist yet -- these two need an update
to an existing row / a genuinely new row respectively)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import app.core.database as database
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "local_demo.sqlite3")
database.engine = create_engine(f"sqlite:///{DB_PATH}")
database.SessionLocal = sessionmaker(bind=database.engine)
from app.models.all import Parser
from seed_vendor_packs import PACKS

db = database.SessionLocal()
try:
    for pack in PACKS:
        if pack["id"] not in ("fortigate_traffic_kv", "nginx_plus_kv", "windows_ntlm_8004_xml"):
            continue
        config_json = yaml.safe_load(pack["config_yaml"])
        existing = db.query(Parser).filter(Parser.id == pack["id"]).first()
        if existing:
            existing.config_yaml = pack["config_yaml"]
            existing.config_json = config_json
            existing.sample_log = pack["sample_log"]
            existing.format_type = pack["format_type"]
            existing.vendor = pack["vendor"]
            existing.device_type = pack["device_type"]
            existing.status = "published"
            print(f"updated: {pack['id']}")
        else:
            db.add(Parser(
                id=pack["id"], name=pack["name"], vendor=pack["vendor"],
                device_type=pack["device_type"], format_type=pack["format_type"],
                version="1.0.0", config_yaml=pack["config_yaml"], config_json=config_json,
                sample_log=pack["sample_log"], status="published", coverage_status="fixture",
                created_by="seed_vendor_packs",
            ))
            print(f"created: {pack['id']}")
    db.commit()
finally:
    db.close()
