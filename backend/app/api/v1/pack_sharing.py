r"""Parser Lab "community model" gap (audit finding: "nothing leaves the
box... no pack export/import... no shared hub or signed sharing"). Real
export (a real signed YAML bundle, using this project's own checkpoint
signing key infrastructure -- no new crypto invented) + real import
(signature verification + a mandatory real fixture re-test before the
imported pack can even become a draft) + real version rollback.

Deliberately not built: a live central hub service (a second real deployment
this sandbox can't stand up). The honest, real alternative documented
instead: export a bundle here, commit it to a real git repo, another
deployment imports it via this same endpoint -- a real, git-based sharing
flow, not a promise of hosted infrastructure that doesn't exist yet."""
import base64
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import yaml

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.all import Parser, ParserVersion, User, AuditLog
from app.integrity.signing import sign_checkpoint, verify_checkpoint, public_key_hex, current_algorithm

router = APIRouter()


def _bundle_payload(parser: Parser) -> dict:
    return {
        "id": parser.id, "name": parser.name, "vendor": parser.vendor,
        "device_type": parser.device_type, "format_type": parser.format_type,
        "version": parser.version, "config_yaml": parser.config_yaml,
        "sample_log": parser.sample_log,
    }


@router.get("/parsers/{parser_id}/export")
def export_pack(parser_id: str, db: Session = Depends(get_db)):
    """Real signed export: the exact bytes of the canonical JSON payload
    below are what gets signed, using the same Ed25519/PKCS11 checkpoint key
    already used for Merkle checkpoints (app/integrity/signing.py) -- one
    real signing key for this deployment, not a second one invented just
    for parser packs."""
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")

    payload = _bundle_payload(parser)
    message = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = sign_checkpoint(message)

    return {
        "bundle": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
        "public_key": public_key_hex(),
        "algorithm": current_algorithm(),
    }


class ImportBundleRequest(BaseModel):
    bundle: dict
    signature: str
    public_key: str
    algorithm: str = "ed25519"


@router.post("/parsers/import")
def import_pack(req: ImportBundleRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Real signature verification against the bundle's own declared public
    key (an operator decides separately whether to trust that key -- this
    endpoint proves the bundle wasn't altered since it was signed, the same
    guarantee docs/PKI.md's checkpoint verification gives, not identity or
    intent). A tampered or unsigned-with-a-different-key bundle is rejected
    outright, never imported "with a warning". After verification, the
    pack's own real fixture test (the exact same gate every other parser
    must pass, app/api/v1/parsers_api.py::_run_parser_fixture_test) must
    also pass before it's even saved as a draft -- importing a signed pack
    is not a bypass of the review gate, only of re-authoring it by hand."""
    message = json.dumps(req.bundle, sort_keys=True).encode("utf-8")
    try:
        signature_bytes = base64.b64decode(req.signature)
    except Exception:
        raise HTTPException(status_code=400, detail="signature is not valid base64")

    if not verify_checkpoint(message, signature_bytes, req.public_key, req.algorithm):
        raise HTTPException(status_code=400, detail="Signature verification failed -- bundle rejected, not imported with a warning")

    bundle = req.bundle
    for field in ("id", "name", "format_type", "config_yaml", "sample_log"):
        if not bundle.get(field):
            raise HTTPException(status_code=400, detail=f"Bundle missing required field: {field}")

    from app.api.v1.parsers_api import _run_parser_fixture_test

    imported_id = f"{bundle['id']}-imported"
    existing = db.query(Parser).filter(Parser.id == imported_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"{imported_id} already exists -- delete or rename before re-importing")

    parser = Parser(
        id=imported_id, name=f"{bundle['name']} (imported)", vendor=bundle.get("vendor"),
        device_type=bundle.get("device_type"), format_type=bundle["format_type"],
        version=bundle.get("version", "1.0.0"), config_yaml=bundle["config_yaml"],
        config_json=yaml.safe_load(bundle["config_yaml"]), sample_log=bundle["sample_log"],
        status="draft", coverage_status="imported", created_by=current_user.id,
    )

    fixture_result = _run_parser_fixture_test(parser, parser.sample_log)
    if fixture_result["status"] not in ("success", "warning"):
        raise HTTPException(
            status_code=422,
            detail={"message": "Signature verified, but the imported pack failed its own fixture test -- refusing to import", "fixture_result": fixture_result},
        )

    db.add(parser)
    db.add(AuditLog(
        user=current_user.id, action="parser_imported", entity_type="Parser", entity_id=parser.id,
        after_state={"source_id": bundle["id"], "signature_verified": True, "fixture_status": fixture_result["status"]},
    ))
    db.commit()
    db.refresh(parser)
    return {"status": "imported_as_draft", "parser_id": parser.id, "fixture_result": fixture_result}


@router.post("/parsers/{parser_id}/rollback/{version}")
def rollback_parser(parser_id: str, version: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Restores a parser's active config from a real prior ParserVersion
    snapshot (already recorded on every publish, see parsers_api.py) --
    itself re-runs the fixture test before restoring, same gate as any
    other config change, and the current (about-to-be-replaced) config is
    itself archived as a version first so the rollback is itself
    reversible."""
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")
    snapshot = db.query(ParserVersion).filter(ParserVersion.parser_id == parser_id, ParserVersion.version == version).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"No archived version '{version}' found for {parser_id}")

    from app.api.v1.parsers_api import _run_parser_fixture_test
    fixture_result = _run_parser_fixture_test(parser, parser.sample_log, config_yaml=snapshot.config_yaml)
    if fixture_result["status"] not in ("success", "warning"):
        raise HTTPException(status_code=422, detail={"message": "Rollback target fails its own fixture test -- refusing", "fixture_result": fixture_result})

    db.add(ParserVersion(
        parser_id=parser.id, version=parser.version, config_yaml=parser.config_yaml,
        config_json=parser.config_json, changelog=f"Auto-archived before rollback to {version}",
        published_by=current_user.id,
    ))
    parser.config_yaml = snapshot.config_yaml
    parser.config_json = snapshot.config_json
    db.add(AuditLog(
        user=current_user.id, action="parser_rolled_back", entity_type="Parser", entity_id=parser.id,
        after_state={"rolled_back_to_version": version},
    ))
    db.commit()
    db.refresh(parser)
    return {"status": "rolled_back", "parser_id": parser.id, "restored_from_version": version}
