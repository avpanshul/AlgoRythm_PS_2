from sqlalchemy.orm import Session
from app.models.all import MappingRegistry
from app.ai.embeddings import embedding_engine
from app.ai.llm import llm_reasoner
from app.core.config import settings
from datetime import datetime, timezone

def resolve_field_mapping(db: Session, vendor: str, device_type: str, raw_field: str, field_value: str, context: str = "") -> dict:
    # 1. Exact approved mapping
    approved = db.query(MappingRegistry).filter(
        MappingRegistry.vendor == vendor,
        MappingRegistry.raw_field == raw_field,
        MappingRegistry.approved == True
    ).first()
    
    if approved:
        return {
            "canonical_field": approved.canonical_field,
            "confidence": 1.0,
            "mapping_type": "registry"
        }
        
    # 2. Embedding Model (Semantic)
    semantic_res = embedding_engine.find_best_mapping(raw_field)
    conf = semantic_res["confidence"]
    
    # 3. Decision Tree
    auto_threshold = settings.CONFIDENCE_THRESHOLDS["auto_approve"]
    review_threshold = settings.CONFIDENCE_THRESHOLDS["review"]
    
    if conf >= auto_threshold:
        return {
            "canonical_field": semantic_res["candidate"],
            "confidence": conf,
            "mapping_type": "semantic"
        }
    
    # Low confidence -> ask LLM
    llm_res = llm_reasoner.ask_mapping(vendor, device_type, raw_field, field_value, context)
    llm_conf = llm_res["confidence"]
    llm_field = llm_res["selected_field"]
    
    if llm_conf >= auto_threshold:
        return {
            "canonical_field": llm_field,
            "confidence": llm_conf,
            "mapping_type": "llm"
        }
        
    # Fallback to human review
    mapping = MappingRegistry(
        vendor=vendor,
        device_type=device_type,
        raw_field=raw_field,
        canonical_field=llm_field if llm_conf > conf else semantic_res["candidate"],
        mapping_type="llm" if llm_conf > conf else "semantic",
        confidence=max(llm_conf, conf),
        approved=False
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    
    return {
        "canonical_field": mapping.canonical_field,
        "confidence": mapping.confidence,
        "mapping_type": "needs_review",
        "registry_id": mapping.id
    }
