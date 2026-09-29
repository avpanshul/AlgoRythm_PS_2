"""Evidence export: bundles everything needed to independently verify one
event's integrity into a single zip -- raw bytes, normalized output, Merkle
inclusion proof, the signed checkpoint it's proven against, parser/schema
versions, and a chain-of-custody report. Verify it with the standalone CLI in
backend/verifier/ (built without importing anything from this app)."""
import io
import json
import os
import zipfile
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.local_storage import read_raw_log
from app.models.all import NormalizedEvent, RawEventMetadata, Checkpoint
from app.integrity import service as integrity_service
from app.integrity import rfc3161 as rfc3161_module

router = APIRouter()

BUNDLE_FORMAT_VERSION = "1.0"

BSA_CERTIFICATE_TEMPLATE = """SECTION 63 CERTIFICATE (Bharatiya Sakshya Adhiniyam, 2023)
DRAFT -- REVIEW WITH LEGAL COUNSEL BEFORE USE. Wording below is a starting
point, not verified legal advice, and has not been confirmed against the
current text of the Act.

Certificate under Section 63, Bharatiya Sakshya Adhiniyam, 2023, in respect of
electronic record produced as evidence.

1. Identification of the electronic record:
   Event ID: {event_id}
   Original raw content hash (SHA-256): {raw_sha256}
   Normalized content hash (SHA-256): {normalized_sha256}

2. Manner of production: The electronic record was produced by the Universal
   Log Pre-processing Framework (ULPF), which captured the record losslessly
   at {received_at} via ingestion protocol "{ingestion_protocol}", computed a
   SHA-256 hash of the raw bytes before any processing, and appended that
   hash to an append-only Merkle log periodically checkpointed and signed
   with an Ed25519 key (see accompanying merkle_proof.json / checkpoint.json).

3. Device particulars: [TO BE COMPLETED -- device/system that produced or
   received the original log, its regular use, and the person having lawful
   control over it at the material time.]

4. Statement of the person in charge: [TO BE COMPLETED AND SIGNED]

This certificate accompanies the evidence bundle generated at {generated_at}.
Independent verification of the enclosed hashes and signature is possible
with the offline verifier tool distributed alongside ULPF, without needing to
trust the system that generated this bundle.
"""


def _build_bundle(db: Session, event_id: str) -> bytes:
    norm_event = db.query(NormalizedEvent).filter(NormalizedEvent.event_id == event_id).first()
    if not norm_event:
        raise HTTPException(status_code=404, detail="Normalized event not found")

    meta = db.query(RawEventMetadata).filter(RawEventMetadata.event_id == event_id).first()
    if not meta:
        raise HTTPException(status_code=404, detail="Raw event metadata not found")

    try:
        raw_content = read_raw_log(meta.raw_location)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read raw evidence: {e}")

    proof = integrity_service.get_inclusion_proof(db, event_id)
    if not proof.get("included"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot export evidence bundle: {proof.get('reason')}. Issue a checkpoint first.",
        )

    generated_at = datetime.now(timezone.utc).isoformat()

    # Additional attestation layers beyond the inclusion proof's own
    # checkpoint sub-object: witness cosignature + RFC 3161 timestamp, if
    # either was obtained for this checkpoint. See docs/EVIDENCE_STANDARDS.md
    # for what each proves and how to verify it independently.
    checkpoint_row = db.query(Checkpoint).filter(Checkpoint.id == proof["checkpoint"]["id"]).first()
    attestations = {
        "consistency_proof_note": (
            "This bundle proves inclusion in the checkpoint above. To additionally prove that "
            "checkpoint is an append-only extension of an earlier one, call "
            "GET /integrity/checkpoints/{earlier_id}/consistency-proof?against="
            f"{checkpoint_row.id if checkpoint_row else proof['checkpoint']['id']} -- see docs/EVIDENCE_STANDARDS.md."
        ),
        "witness": None,
        "rfc3161": {"status": "not_configured"},
    }
    if checkpoint_row:
        if checkpoint_row.witness_signature:
            attestations["witness"] = {
                "source": checkpoint_row.witness_source,
                "public_key": checkpoint_row.witness_public_key,
                "signature": checkpoint_row.witness_signature,
                "algorithm": checkpoint_row.witness_algorithm,
                "witnessed_at": checkpoint_row.witnessed_at.isoformat() if checkpoint_row.witnessed_at else None,
            }
        attestations["rfc3161"] = {"status": checkpoint_row.rfc3161_status or "not_configured"}
        if checkpoint_row.rfc3161_token_b64:
            attestations["rfc3161"]["tsa_url"] = checkpoint_row.rfc3161_tsa_url
            attestations["rfc3161"]["token_b64"] = checkpoint_row.rfc3161_token_b64
            attestations["rfc3161"]["summary"] = rfc3161_module.decode_token_summary(checkpoint_row.rfc3161_token_b64)
            attestations["rfc3161"]["verify_command"] = (
                "openssl ts -verify -token_in -in token.der -data message.bin -CAfile <tsa-ca.pem> "
                "-untrusted <tsa-intermediate.pem>  # message.bin = literal bytes "
                f'"{checkpoint_row.tree_size}:{checkpoint_row.root_hash}"'
            )
        if checkpoint_row.last_verification_status:
            attestations["scheduled_reverification"] = {
                "status": checkpoint_row.last_verification_status,
                "last_verified_at": checkpoint_row.last_verified_at.isoformat() if checkpoint_row.last_verified_at else None,
            }

    custody_report = {
        "event_id": event_id,
        "source_id": meta.source_id,
        "received_at": meta.received_at.isoformat() if meta.received_at else None,
        "ingestion_protocol": meta.ingestion_protocol,
        "raw_sha256": meta.raw_sha256,
        "raw_location": meta.raw_location,
        "processing_status": meta.processing_status,
        "normalized_sha256": norm_event.normalized_sha256,
        "parser_id": norm_event.parser_id,
        "parser_version": norm_event.parser_version,
        "parser_format": norm_event.parser_format,
        "mapping_method": norm_event.mapping_method,
        "generated_at": generated_at,
        "note": (
            "This report and the accompanying hashes describe this system's own record of "
            "custody. The Merkle inclusion proof and Ed25519-signed checkpoint in this bundle "
            "are what let an independent party verify the raw content and its position in the "
            "log haven't been altered, without trusting this system -- see the standalone "
            "offline verifier."
        ),
    }

    bsa_certificate = BSA_CERTIFICATE_TEMPLATE.format(
        event_id=event_id,
        raw_sha256=meta.raw_sha256,
        normalized_sha256=norm_event.normalized_sha256,
        received_at=meta.received_at.isoformat() if meta.received_at else "unknown",
        ingestion_protocol=meta.ingestion_protocol,
        generated_at=generated_at,
    )

    files = {
        "raw_event.txt": raw_content.encode("utf-8"),
        "normalized_event.json": json.dumps(norm_event.canonical_json, indent=2).encode("utf-8"),
        "merkle_proof.json": json.dumps(proof, indent=2).encode("utf-8"),
        "chain_of_custody.json": json.dumps(custody_report, indent=2).encode("utf-8"),
        "attestations.json": json.dumps(attestations, indent=2).encode("utf-8"),
        "bsa_section63_certificate_DRAFT.txt": bsa_certificate.encode("utf-8"),
    }

    manifest = {
        "bundle_format_version": BUNDLE_FORMAT_VERSION,
        "event_id": event_id,
        "generated_at": generated_at,
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
    }
    files["manifest.json"] = json.dumps(manifest, indent=2).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf.read()


@router.get("/evidence/bundle/{event_id}")
def export_evidence_bundle(event_id: str, db: Session = Depends(get_db)):
    bundle_bytes = _build_bundle(db, event_id)
    return StreamingResponse(
        io.BytesIO(bundle_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="evidence_{event_id}.zip"'},
    )


# repo_root/verifier/verify_bundle.py -- backend/app/api/v1/evidence.py is 4 dirs deep
_VERIFIER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    "verifier", "verify_bundle.py",
)


@router.get("/evidence/verifier")
def download_verifier():
    """Serves the standalone offline verifier script -- it has no dependency
    on this app (see verifier/verify_bundle.py's own docstring), this is just
    a convenient download path."""
    if not os.path.exists(_VERIFIER_PATH):
        raise HTTPException(status_code=404, detail="Verifier script not found on this server")
    return FileResponse(_VERIFIER_PATH, media_type="text/x-python", filename="verify_bundle.py")
