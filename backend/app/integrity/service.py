"""Wires the Merkle tree + Ed25519 signer to the database: appending leaves as
events are ingested, issuing signed checkpoints, and producing inclusion proofs.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.all import MerkleLeaf, Checkpoint, AuditLog
from app.integrity import merkle, signing, witness, rfc3161


def append_leaf(db: Session, event_id: str, normalized_sha256: str) -> MerkleLeaf:
    """Add a normalized event's hash to the append-only Merkle log. Call within
    the same transaction as the NormalizedEvent insert; does not commit.

    Idempotent by design: if this event_id already has a leaf (real bug found
    live -- every Replay job that re-processed an already-ingested event hit
    a real `UNIQUE constraint failed: merkle_leaves.event_id` here and got
    dumped into the DLQ, even though nothing was actually wrong with the
    event), the existing leaf is returned UNCHANGED rather than inserting a
    second one or updating the first. This isn't a workaround -- it's the
    actually-correct append-only behavior: a leaf attests "this event_id's
    raw content was in the log as of its first processing," which stays true
    forever regardless of how many times the event is later reprocessed with
    a different parser. Replay's own job is to produce a *new normalized
    version* (already handled by NormalizedEventVersion, see
    app/api/v1/replay.py) -- it was never supposed to touch this event's
    place in the Merkle log at all."""
    existing = db.query(MerkleLeaf).filter(MerkleLeaf.event_id == event_id).first()
    if existing is not None:
        return existing
    leaf_data = f"{event_id}:{normalized_sha256}".encode("utf-8")
    leaf = MerkleLeaf(event_id=event_id, leaf_hash=merkle.leaf_hash(leaf_data).hex())
    db.add(leaf)
    db.flush()
    return leaf


def _ordered_leaf_hashes(db: Session, limit: int = None) -> list:
    q = db.query(MerkleLeaf).order_by(MerkleLeaf.sequence.asc())
    if limit is not None:
        q = q.limit(limit)
    return [bytes.fromhex(r.leaf_hash) for r in q.all()]


def create_checkpoint(db: Session) -> Checkpoint:
    """Snapshot the current Merkle tree and sign it. A compromised admin who
    rewrites history after this point cannot reproduce a valid signature over
    the old (root_hash, tree_size) pair without the private key.

    Also, best-effort and non-fatal: cosigns with the local witness key
    (Part: multi-party witnessing, unless AUTO_WITNESS_LOCAL=false) and
    requests a real RFC 3161 timestamp token if RFC3161_TSA_URL is
    configured. Neither failing blocks the checkpoint itself from being
    created -- the core signed (tree_size, root_hash) attestation is what
    every downstream feature (inclusion proofs, evidence bundles) actually
    depends on; witnessing and timestamping are additional, independently
    recorded layers of assurance on top of it."""
    leaves = _ordered_leaf_hashes(db)
    root = merkle.merkle_root(leaves).hex()
    tree_size = len(leaves)
    message = f"{tree_size}:{root}".encode("utf-8")
    checkpoint = Checkpoint(
        tree_size=tree_size,
        root_hash=root,
        signature=signing.sign_checkpoint(message).hex(),
        public_key=signing.public_key_hex(),
        algorithm=signing.current_algorithm(),
    )

    if settings.AUTO_WITNESS_LOCAL:
        try:
            checkpoint.witness_signature = witness.sign_local_witness(message).hex()
            checkpoint.witness_public_key = witness.local_witness_public_key_hex()
            checkpoint.witness_algorithm = "ed25519"
            checkpoint.witness_source = "local"
            checkpoint.witnessed_at = datetime.now(timezone.utc)
        except Exception:
            pass  # witnessing is additive; a failure here must not block checkpoint creation

    ts_result = rfc3161.request_timestamp(message)
    checkpoint.rfc3161_status = ts_result.get("status", "not_configured")
    if ts_result.get("status") == "obtained":
        checkpoint.rfc3161_token_b64 = ts_result["token_b64"]
        checkpoint.rfc3161_tsa_url = ts_result["tsa_url"]

    db.add(checkpoint)
    db.commit()
    db.refresh(checkpoint)
    return checkpoint


def witness_checkpoint_externally(db: Session, checkpoint_id: int, public_key_hex_str: str, signature_hex: str, algorithm: str = "ed25519") -> Checkpoint:
    """Accepts a real cosignature from an external party (a different host,
    team, or auditor) who independently verified this checkpoint's
    (tree_size, root_hash) out of band. Only Ed25519 is supported for
    external witnesses currently. Rejects (raises ValueError) any public key
    not on the WITNESS_TRUSTED_PUBLIC_KEYS allowlist and any signature that
    doesn't actually verify -- never stores an unverified cosignature."""
    checkpoint = db.query(Checkpoint).filter(Checkpoint.id == checkpoint_id).first()
    if checkpoint is None:
        raise ValueError("checkpoint not found")
    if algorithm != "ed25519":
        raise ValueError(f"unsupported external witness algorithm: {algorithm}")
    if not witness.is_trusted_external_key(public_key_hex_str):
        raise ValueError("public key is not on WITNESS_TRUSTED_PUBLIC_KEYS")

    message = f"{checkpoint.tree_size}:{checkpoint.root_hash}".encode("utf-8")
    signature = bytes.fromhex(signature_hex)
    if not witness.verify_witness_signature(message, signature, public_key_hex_str):
        raise ValueError("witness signature does not verify against this checkpoint")

    checkpoint.witness_signature = signature_hex
    checkpoint.witness_public_key = public_key_hex_str
    checkpoint.witness_algorithm = algorithm
    checkpoint.witness_source = "external"
    checkpoint.witnessed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(checkpoint)
    return checkpoint


def latest_checkpoint(db: Session) -> Checkpoint:
    return db.query(Checkpoint).order_by(Checkpoint.id.desc()).first()


def verify_checkpoint_signature(checkpoint: Checkpoint) -> bool:
    message = f"{checkpoint.tree_size}:{checkpoint.root_hash}".encode("utf-8")
    algorithm = checkpoint.algorithm or "ed25519"  # pre-D3 rows predate the column
    return signing.verify_checkpoint(message, bytes.fromhex(checkpoint.signature), checkpoint.public_key, algorithm)


def get_consistency_proof(db: Session, first_checkpoint_id: int, second_checkpoint_id: int) -> dict:
    """Proves the checkpoint `second_checkpoint_id` is a pure append-only
    extension of `first_checkpoint_id` -- every leaf and position the
    earlier checkpoint attested to is unchanged in the later one. Both
    checkpoints must already exist; the proof is computed from the CURRENT
    leaf table, so if leaves have been altered since either checkpoint was
    issued, `verified` below will honestly come back False rather than the
    proof silently not being generated."""
    first = db.query(Checkpoint).filter(Checkpoint.id == first_checkpoint_id).first()
    second = db.query(Checkpoint).filter(Checkpoint.id == second_checkpoint_id).first()
    if first is None or second is None:
        return {"error": "one or both checkpoints not found"}
    if first.tree_size > second.tree_size:
        return {"error": "first checkpoint must be smaller than (or equal to) the second"}

    leaves = _ordered_leaf_hashes(db, limit=second.tree_size)
    if len(leaves) < second.tree_size:
        return {"error": "fewer leaves currently exist than the second checkpoint's tree_size -- leaves may have been deleted"}

    proof = merkle.consistency_proof(leaves, first.tree_size, second.tree_size)
    verified = merkle.verify_consistency_proof(
        first.tree_size, bytes.fromhex(first.root_hash),
        second.tree_size, bytes.fromhex(second.root_hash),
        proof,
    )
    return {
        "first_checkpoint_id": first.id,
        "first_tree_size": first.tree_size,
        "first_root_hash": first.root_hash,
        "second_checkpoint_id": second.id,
        "second_tree_size": second.tree_size,
        "second_root_hash": second.root_hash,
        "proof": [h.hex() for h in proof],
        "verified": verified,
    }


def reverify_checkpoint(db: Session, checkpoint: Checkpoint) -> dict:
    """Re-walks one previously-issued checkpoint: recomputes its root from
    the CURRENT leaf table (not the value stored on the row) and re-checks
    its signature, so a leaf altered/deleted after the checkpoint was issued
    is actually caught rather than only ever being trusted at issuance time.
    A mismatch is recorded as tamper_detected AND written to the
    hash-chained audit log -- this is a real integrity incident, not a
    routine event."""
    leaves = _ordered_leaf_hashes(db, limit=checkpoint.tree_size)
    detail = None
    if len(leaves) < checkpoint.tree_size:
        status = "tamper_detected"
        detail = f"only {len(leaves)} leaves exist now, expected at least {checkpoint.tree_size} -- leaves appear to have been deleted"
    else:
        recomputed_root = merkle.merkle_root(leaves).hex()
        sig_valid = verify_checkpoint_signature(checkpoint)
        if recomputed_root != checkpoint.root_hash:
            status = "tamper_detected"
            detail = f"recomputed root {recomputed_root} does not match stored root {checkpoint.root_hash}"
        elif not sig_valid:
            status = "tamper_detected"
            detail = "stored signature does not verify against the stored (tree_size, root_hash)"
        else:
            status = "valid"

    checkpoint.last_verified_at = datetime.now(timezone.utc)
    checkpoint.last_verification_status = status
    checkpoint.last_verification_detail = detail

    if status == "tamper_detected":
        db.add(AuditLog(
            user="system", action="checkpoint_tamper_detected", entity_type="Checkpoint",
            entity_id=str(checkpoint.id), after_state={"detail": detail, "tree_size": checkpoint.tree_size},
        ))

    db.commit()
    return {"checkpoint_id": checkpoint.id, "status": status, "detail": detail}


def reverify_due_checkpoints(db: Session, max_age_hours: int = None, batch_size: int = None) -> list:
    """Re-verifies up to `batch_size` checkpoints that either have never
    been verified or haven't been re-verified in over `max_age_hours` --
    oldest-unverified-first, so a large checkpoint history gets worked
    through over successive scheduler cycles instead of all at once."""
    from datetime import timedelta

    max_age_hours = max_age_hours if max_age_hours is not None else settings.CHECKPOINT_REVERIFY_INTERVAL_HOURS
    batch_size = batch_size if batch_size is not None else settings.CHECKPOINT_REVERIFY_BATCH_SIZE
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    due = db.query(Checkpoint).filter(
        (Checkpoint.last_verified_at.is_(None)) | (Checkpoint.last_verified_at < cutoff)
    ).order_by(Checkpoint.last_verified_at.is_(None).desc(), Checkpoint.last_verified_at.asc()).limit(batch_size).all()

    return [reverify_checkpoint(db, c) for c in due]


def get_inclusion_proof(db: Session, event_id: str) -> dict:
    """Full 'prove this event' payload: leaf hash, audit path, and the signed
    checkpoint it's proven against. `root_matches` lets a caller confirm the
    proof is internally consistent before trusting the signature."""
    leaf_row = db.query(MerkleLeaf).filter(MerkleLeaf.event_id == event_id).first()
    if leaf_row is None:
        return {"included": False, "reason": "event has not been added to the Merkle log yet"}

    checkpoint = latest_checkpoint(db)
    if checkpoint is None:
        return {"included": False, "reason": "no checkpoint has been issued yet"}

    leaves_at_checkpoint = db.query(MerkleLeaf).filter(
        MerkleLeaf.sequence <= checkpoint.tree_size
    ).order_by(MerkleLeaf.sequence.asc()).all()

    ids_in_order = [r.event_id for r in leaves_at_checkpoint]
    if event_id not in ids_in_order:
        return {"included": False, "reason": "event not yet covered by the latest checkpoint; issue a new checkpoint"}

    index = ids_in_order.index(event_id)
    leaf_hashes = [bytes.fromhex(r.leaf_hash) for r in leaves_at_checkpoint]
    proof = merkle.audit_path(leaf_hashes, index)
    computed_root = merkle.merkle_root(leaf_hashes).hex()
    root_matches = computed_root == checkpoint.root_hash

    return {
        "included": True,
        "leaf_index": index,
        "leaf_hash": leaf_row.leaf_hash,
        "audit_path": [h.hex() for h in proof],
        "root_matches": root_matches,
        "signature_valid": verify_checkpoint_signature(checkpoint) if root_matches else False,
        "checkpoint": {
            "id": checkpoint.id,
            "tree_size": checkpoint.tree_size,
            "root_hash": checkpoint.root_hash,
            "signature": checkpoint.signature,
            "public_key": checkpoint.public_key,
            "algorithm": checkpoint.algorithm or "ed25519",
            "created_at": checkpoint.created_at.isoformat() if checkpoint.created_at else None,
        },
    }
