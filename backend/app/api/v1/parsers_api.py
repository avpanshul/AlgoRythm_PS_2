"""Parser Registry API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import yaml
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.all import Parser, ParserVersion, AuditLog, User
from app.core.processing import process_raw_event

router = APIRouter()

class ParserCreate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    vendor: Optional[str] = None
    device_type: Optional[str] = None
    format_type: str
    version: str = "1.0.0"
    config_yaml: str
    sample_log: Optional[str] = None

class ParserUpdate(BaseModel):
    name: str = None
    description: str = None
    vendor: str = None
    device_type: str = None
    format_type: str = None
    config_yaml: str = None
    sample_log: str = None
    
class TestParserRequest(BaseModel):
    sample_log: str
    config_yaml: Optional[str] = None


@router.get("/parsers")
def list_parsers(db: Session = Depends(get_db)):
    parsers = db.query(Parser).order_by(Parser.created_at.desc()).all()
    return parsers


@router.post("/parsers")
def create_parser(req: ParserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing = db.query(Parser).filter(Parser.id == req.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Parser ID already exists")

    try:
        config_json = yaml.safe_load(req.config_yaml)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")

    parser = Parser(
        id=req.id,
        name=req.name,
        description=req.description,
        vendor=req.vendor,
        device_type=req.device_type,
        format_type=req.format_type,
        version=req.version,
        config_yaml=req.config_yaml,
        config_json=config_json,
        sample_log=req.sample_log,
        status="draft",
        created_by=current_user.id,
    )
    db.add(parser)
    db.commit()
    db.refresh(parser)

    audit = AuditLog(user=current_user.id, action="parser_created", entity_type="Parser", entity_id=parser.id)
    db.add(audit)
    db.commit()

    return parser


@router.get("/parsers/{parser_id}")
def get_parser(parser_id: str, db: Session = Depends(get_db)):
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")
    return parser


@router.put("/parsers/{parser_id}")
def update_parser(parser_id: str, req: ParserUpdate, db: Session = Depends(get_db)):
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")
        
    for k, v in req.model_dump(exclude_unset=True).items():
        if k == "config_yaml" and v:
            try:
                parser.config_json = yaml.safe_load(v)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
        setattr(parser, k, v)
        
    parser.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(parser)
    
    return parser


def _run_parser_fixture_test(parser: Parser, sample_log: str, config_yaml: str = None) -> dict:
    """Runs the parser's own config against `sample_log` in an isolated,
    time-limited OS process (app/parsers/sandbox.py, ULPF-master-prompt.md
    Part D6) -- this is the exact moment an operator's untrusted sample text
    gets executed against a parser, so it's the boundary that needs
    sandboxing, not the bulk ingestion path (see that module's docstring).
    This is the fixture score a parser has to pass before it can be
    published -- see publish_parser below."""
    from app.parsers.sandbox import run_parser_fixture_sandboxed

    config_yaml_to_use = config_yaml if config_yaml else parser.config_yaml
    return run_parser_fixture_sandboxed(sample_log, parser.format_type, config_yaml_to_use)


@router.post("/parsers/{parser_id}/test")
def test_parser(parser_id: str, req: TestParserRequest, db: Session = Depends(get_db)):
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")

    return _run_parser_fixture_test(parser, req.sample_log, req.config_yaml)


@router.post("/parsers/{parser_id}/publish")
def publish_parser(parser_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")

    # Separation of duties (ULPF-master-prompt.md Part D1): a parser author
    # cannot approve/publish their own parser. Enforced against the real
    # authenticated actor -- create_parser now records the real current_user.id
    # as created_by, not a hardcoded "admin", so this check actually means
    # something rather than always comparing "admin" to itself.
    if parser.created_by and parser.created_by == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Separation of duties: you authored this parser and cannot also publish it. "
                   "A different user must review and publish it.",
        )
    if current_user.role_name not in ("admin", "approver"):
        raise HTTPException(
            status_code=403,
            detail="Only an 'approver' or 'admin' role may publish a parser.",
        )

    # Human-approval gate, scored against a fixture: a parser can't be published
    # without a sample log on file, and that sample has to actually parse and
    # normalize cleanly through the parser's own config -- not just look
    # syntactically valid as YAML.
    if not parser.sample_log:
        raise HTTPException(status_code=400, detail="Cannot publish a parser with no sample_log to test against")

    fixture_result = _run_parser_fixture_test(parser, parser.sample_log)
    if fixture_result["status"] not in ("success", "warning"):
        raise HTTPException(
            status_code=400,
            detail=f"Parser failed its fixture test, refusing to publish: {fixture_result.get('error')}",
        )

    # Bump minor version for demo
    v_parts = parser.version.split('.')
    v_parts[-1] = str(int(v_parts[-1]) + 1)
    new_version = ".".join(v_parts)

    # Save old version
    pv = ParserVersion(
        parser_id=parser.id,
        version=parser.version,
        config_yaml=parser.config_yaml,
        config_json=parser.config_json,
        published_by=current_user.id,
    )
    db.add(pv)

    # Update current
    parser.version = new_version
    parser.status = "published"
    parser.updated_at = datetime.now(timezone.utc)

    audit = AuditLog(
        user=current_user.id, action="parser_published", entity_type="Parser", entity_id=parser.id,
        after_state={"fixture_test_status": fixture_result["status"], "version": new_version},
    )
    db.add(audit)
    db.commit()

    # Item 3: backlog re-parse -- a bounded background task (own thread, own
    # DB session), never blocks this response. No-op (logged internally) if
    # ENABLE_AUTO_REPARSE is off or this parser has no real originating DLQ
    # cluster (see auto_reparse.py:cluster_id_for_parser's docstring).
    from app.services.auto_reparse import trigger_background_reparse
    trigger_background_reparse(parser.id, published_by=current_user.id)

    return parser


@router.get("/parsers/{parser_id}/versions")
def list_parser_versions(parser_id: str, db: Session = Depends(get_db)):
    versions = db.query(ParserVersion).filter(ParserVersion.parser_id == parser_id).order_by(ParserVersion.created_at.desc()).all()
    return versions


@router.get("/parsers-coverage-matrix")
def get_coverage_matrix(db: Session = Depends(get_db)):
    """Auto-generated from the parser registry itself -- never hand-maintained,
    so it can't silently drift from what's actually registered. `coverage_status`
    is never "verified" unless a parser was explicitly marked as having matched
    real production traffic (see Parser.coverage_status)."""
    parsers = db.query(Parser).order_by(Parser.vendor, Parser.name).all()
    return {
        "generated_from": "live parser registry",
        "total_parsers": len(parsers),
        "packs": [
            {
                "id": p.id,
                "name": p.name,
                "vendor": p.vendor,
                "device_type": p.device_type,
                "format_type": p.format_type,
                "status": p.status,
                "coverage_status": p.coverage_status,
                "version": p.version,
            }
            for p in parsers
        ],
    }
