"""Parser Registry API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import yaml
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.all import Parser, ParserVersion, AuditLog
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
def create_parser(req: ParserCreate, db: Session = Depends(get_db)):
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
        created_by="admin"
    )
    db.add(parser)
    db.commit()
    db.refresh(parser)
    
    audit = AuditLog(user="admin", action="parser_created", entity_type="Parser", entity_id=parser.id)
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


@router.post("/parsers/{parser_id}/test")
def test_parser(parser_id: str, req: TestParserRequest, db: Session = Depends(get_db)):
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")
        
    # Mocking actual parser testing using the core pipeline logic for demo
    # In reality, this would evaluate the YAML mapping
    try:
        # Simulate testing by running through standard deterministic parsers
        from app.parsers.deterministic import parse_log
        from app.core.processing import normalize_parsed_data, redact_pii
        
        parsed = parse_log(req.sample_log, parser.format_type)
        if not parsed or parsed == {}:
            return {"status": "failed", "error": "Parser returned no data", "parsed": None, "normalized": None}
            
        normalized = normalize_parsed_data(parsed, parser.format_type, req.sample_log)
        redacted_message, _ = redact_pii(normalized.get("message") or "")
        normalized["message"] = redacted_message
        
        # Verify schema
        required_fields = ["event_data", "source_ip"]
        missing = [f for f in required_fields if not normalized.get(f)]
        
        return {
            "status": "success" if not missing else "warning",
            "parsed_raw": parsed,
            "normalized_ecs": normalized,
            "missing_required_fields": missing
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "parsed": None, "normalized": None}


@router.post("/parsers/{parser_id}/publish")
def publish_parser(parser_id: str, db: Session = Depends(get_db)):
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")
        
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
        published_by="admin"
    )
    db.add(pv)
    
    # Update current
    parser.version = new_version
    parser.status = "published"
    parser.updated_at = datetime.now(timezone.utc)
    
    audit = AuditLog(user="admin", action="parser_published", entity_type="Parser", entity_id=parser.id)
    db.add(audit)
    db.commit()
    
    return parser


@router.get("/parsers/{parser_id}/versions")
def list_parser_versions(parser_id: str, db: Session = Depends(get_db)):
    versions = db.query(ParserVersion).filter(ParserVersion.parser_id == parser_id).order_by(ParserVersion.created_at.desc()).all()
    return versions
