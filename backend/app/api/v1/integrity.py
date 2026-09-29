"""Merkle checkpoint + inclusion-proof API. Backs the "Prove this event" button
and the standalone offline verifier."""
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.config import settings
from app.models.all import Checkpoint, User
from app.integrity import service as integrity_service
from app.integrity import witness as witness_module
from app.integrity import rfc3161 as rfc3161_module

router = APIRouter()


def _checkpoint_dict(c: Checkpoint) -> dict:
    return {
        "id": c.id,
        "tree_size": c.tree_size,
        "root_hash": c.root_hash,
        "signature": c.signature,
        "public_key": c.public_key,
        "algorithm": c.algorithm or "ed25519",
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "last_verified_at": c.last_verified_at.isoformat() if c.last_verified_at else None,
        "last_verification_status": c.last_verification_status,
        "witness": {
            "source": c.witness_source,
            "public_key": c.witness_public_key,
            "algorithm": c.witness_algorithm,
            "witnessed_at": c.witnessed_at.isoformat() if c.witnessed_at else None,
        } if c.witness_signature else None,
        "rfc3161": {
            "status": c.rfc3161_status or "not_configured",
            "tsa_url": c.rfc3161_tsa_url,
        },
    }


@router.post("/integrity/checkpoints")
def create_checkpoint(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    checkpoint = integrity_service.create_checkpoint(db)
    return _checkpoint_dict(checkpoint)


@router.get("/integrity/checkpoints")
def list_checkpoints(db: Session = Depends(get_db)):
    rows = db.query(Checkpoint).order_by(Checkpoint.id.desc()).limit(50).all()
    return [_checkpoint_dict(c) for c in rows]


@router.get("/integrity/checkpoints/latest")
def get_latest_checkpoint(db: Session = Depends(get_db)):
    checkpoint = integrity_service.latest_checkpoint(db)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="No checkpoint has been issued yet")
    return {
        **_checkpoint_dict(checkpoint),
        "signature_valid": integrity_service.verify_checkpoint_signature(checkpoint),
    }


@router.get("/events/{event_id}/proof")
def get_event_proof(event_id: str, db: Session = Depends(get_db)):
    proof = integrity_service.get_inclusion_proof(db, event_id)
    return proof


@router.get("/integrity/checkpoints/{checkpoint_id}/consistency-proof")
def get_consistency_proof(checkpoint_id: int, against: int, db: Session = Depends(get_db)):
    """Proves the checkpoint at `against` (must be the larger/later one) is
    an append-only extension of `checkpoint_id`. GET .../5/consistency-proof?against=12
    proves checkpoint 12 grew out of checkpoint 5 without anything in
    between being altered or removed."""
    result = integrity_service.get_consistency_proof(db, checkpoint_id, against)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/integrity/checkpoints/{checkpoint_id}/reverify")
def reverify_checkpoint_now(checkpoint_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """On-demand re-walk of one checkpoint (the same check the background
    scheduler runs periodically) -- lets an operator verify a specific
    checkpoint right now rather than waiting for its next scheduled turn."""
    checkpoint = db.query(Checkpoint).filter(Checkpoint.id == checkpoint_id).first()
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return integrity_service.reverify_checkpoint(db, checkpoint)


@router.get("/integrity/witness/public-key")
def get_local_witness_public_key():
    """This instance's own local witness public key -- what an external
    party would need to independently verify a checkpoint's cosignature, and
    what an operator adds to another instance's WITNESS_TRUSTED_PUBLIC_KEYS
    to accept cosignatures back from this one."""
    return {"algorithm": "ed25519", "public_key": witness_module.local_witness_public_key_hex()}


@router.post("/integrity/checkpoints/{checkpoint_id}/witness")
def witness_checkpoint_locally(checkpoint_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role("admin", "auditor"))):
    """Cosigns a checkpoint with this instance's local witness key on demand
    (checkpoints are already auto-witnessed at creation by default -- see
    AUTO_WITNESS_LOCAL -- this is for a checkpoint created before witnessing
    was enabled, or with AUTO_WITNESS_LOCAL=false)."""
    checkpoint = db.query(Checkpoint).filter(Checkpoint.id == checkpoint_id).first()
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    from datetime import datetime, timezone
    message = f"{checkpoint.tree_size}:{checkpoint.root_hash}".encode("utf-8")
    checkpoint.witness_signature = witness_module.sign_local_witness(message).hex()
    checkpoint.witness_public_key = witness_module.local_witness_public_key_hex()
    checkpoint.witness_algorithm = "ed25519"
    checkpoint.witness_source = "local"
    checkpoint.witnessed_at = datetime.now(timezone.utc)
    db.commit()
    return _checkpoint_dict(checkpoint)


class ExternalWitnessRequest(BaseModel):
    public_key: str
    signature: str
    algorithm: str = "ed25519"


@router.post("/integrity/checkpoints/{checkpoint_id}/witness-external")
def witness_checkpoint_externally(checkpoint_id: int, req: ExternalWitnessRequest, db: Session = Depends(get_db), current_user: User = Depends(require_role("admin", "auditor"))):
    """Accepts a real cosignature an external party computed independently
    over this checkpoint's (tree_size, root_hash) -- see
    integrity_service.witness_checkpoint_externally's docstring. The public
    key must already be on WITNESS_TRUSTED_PUBLIC_KEYS; this never silently
    trusts a new key on first submission."""
    try:
        checkpoint = integrity_service.witness_checkpoint_externally(
            db, checkpoint_id, req.public_key, req.signature, req.algorithm,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _checkpoint_dict(checkpoint)


@router.get("/integrity/checkpoints/{checkpoint_id}/rfc3161")
def get_checkpoint_timestamp(checkpoint_id: int, db: Session = Depends(get_db)):
    """Returns the RFC 3161 timestamp token status for one checkpoint, plus
    a best-effort decoded summary (signing time, serial, policy OID) when a
    token was obtained. Full CMS signature-chain verification is done via
    `openssl ts -verify` -- see the evidence bundle / docs/EVIDENCE_STANDARDS.md
    for the exact command, since that's the standard tool for this, not a
    bespoke reimplementation here."""
    checkpoint = db.query(Checkpoint).filter(Checkpoint.id == checkpoint_id).first()
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    result = {"status": checkpoint.rfc3161_status or "not_configured", "tsa_url": checkpoint.rfc3161_tsa_url}
    if checkpoint.rfc3161_token_b64:
        result["summary"] = rfc3161_module.decode_token_summary(checkpoint.rfc3161_token_b64)
        result["token_b64"] = checkpoint.rfc3161_token_b64
    return result
