"""Platform settings: a small, real key-value store for the handful of
Settings-page controls that actually have a real feature behind them.
Deliberately narrow -- SETTING_KEYS is the whitelist of keys this endpoint
will read or write; a request for anything else is rejected rather than
silently accepted into a schema-less bucket, so this can't quietly grow into
a place to stash values nothing ever reads."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.all import PlatformSetting, User

router = APIRouter()

SETTING_KEYS = {
    "platform_name": "SANKET ULPF",
    "default_timezone": "UTC",
    "session_timeout_minutes": 480,
}


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    rows = {r.key: r.value for r in db.query(PlatformSetting).all()}
    return {key: rows.get(key, default) for key, default in SETTING_KEYS.items()}


@router.put("/settings")
def update_settings(req: SettingsUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    unknown = set(req.values.keys()) - set(SETTING_KEYS.keys())
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown setting key(s): {', '.join(sorted(unknown))}")

    for key, value in req.values.items():
        row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
        if row:
            row.value = value
            row.updated_by = current_user.id
        else:
            db.add(PlatformSetting(key=key, value=value, updated_by=current_user.id))
    db.commit()

    rows = {r.key: r.value for r in db.query(PlatformSetting).all()}
    return {key: rows.get(key, default) for key, default in SETTING_KEYS.items()}
