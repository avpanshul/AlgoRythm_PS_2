"""Integrations API."""
import socket
import time

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.all import Integration, AuditLog

router = APIRouter()

class IntegrationCreate(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    config: dict
    enabled: bool = True

class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None
    enabled: Optional[bool] = None


@router.get("/integrations")
def list_integrations(db: Session = Depends(get_db)):
    return db.query(Integration).all()


@router.post("/integrations")
def create_integration(req: IntegrationCreate, db: Session = Depends(get_db)):
    integration = Integration(
        name=req.name,
        type=req.type,
        description=req.description,
        config=req.config,
        enabled=req.enabled,
        status="configured"
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


@router.put("/integrations/{integration_id}")
def update_integration(integration_id: int, req: IntegrationUpdate, db: Session = Depends(get_db)):
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
        
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(integration, k, v)
        
    integration.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(integration)
    return integration


@router.delete("/integrations/{integration_id}")
def delete_integration(integration_id: int, db: Session = Depends(get_db)):
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    db.delete(integration)
    db.commit()
    return {"status": "deleted"}


def _run_connectivity_test(integration: Integration) -> dict:
    """Real, kind-specific connectivity check against `integration.config` --
    never a canned "success". webhook/rest_api do a real HTTP request; s3/
    opensearch/syslog do a real TCP connect if a host:port is configured;
    anything else (or missing config) honestly reports it can't be tested
    from here rather than claiming a fake success."""
    config = integration.config or {}
    start = time.monotonic()

    if integration.type in ("webhook", "rest_api"):
        url = config.get("url")
        if not url:
            return {"status": "error", "message": "config.url is not set -- nothing to connect to"}
        try:
            resp = requests.get(url, timeout=5)
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            ok = resp.status_code < 500
            return {
                "status": "success" if ok else "error",
                "latency_ms": latency_ms,
                "http_status": resp.status_code,
                "message": f"Real HTTP GET to {url} returned {resp.status_code}",
            }
        except requests.RequestException as e:
            return {"status": "error", "message": f"Real connection attempt to {url} failed: {e}"}

    host, port = config.get("host"), config.get("port")
    if host and port:
        try:
            with socket.create_connection((host, int(port)), timeout=5):
                latency_ms = round((time.monotonic() - start) * 1000, 1)
            return {"status": "success", "latency_ms": latency_ms, "message": f"Real TCP connect to {host}:{port} succeeded"}
        except OSError as e:
            return {"status": "error", "message": f"Real TCP connect to {host}:{port} failed: {e}"}

    return {
        "status": "not_tested",
        "message": f"No config.url or config.host+config.port set for this '{integration.type}' integration -- nothing to actually test",
    }


@router.post("/integrations/{integration_id}/test")
def test_integration(integration_id: int, db: Session = Depends(get_db)):
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    result = _run_connectivity_test(integration)
    integration.status = "connected" if result["status"] == "success" else ("error" if result["status"] == "error" else "configured")
    integration.last_test_at = datetime.now(timezone.utc)
    integration.last_test_result = result

    db.commit()
    return {"status": result["status"], "result": result}
