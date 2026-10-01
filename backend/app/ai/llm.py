import json
import requests
from pydantic import BaseModel
from app.core.config import settings
# Real bug found live: this used to import `embedding_engine` from
# app.ai.embeddings just to read its static canonical_fields list, which
# force-instantiated that module's EmbeddingEngine() -- a real
# SentenceTransformer load (torch + model weights) plus 16 real embedding
# computations -- inside whatever HTTP request first triggered an
# LLM-fallback field classification. Confirmed via Render's own oomKilled
# event: that one-time heavy load was enough to OOM-kill the 512Mi instance.
# This module never actually uses the embedding model, only the plain field
# list, so importing the lightweight constant directly avoids pulling in
# sentence-transformers/torch at all on this path.
from app.ai.canonical_fields import CANONICAL_FIELDS

class LLMMappingResponse(BaseModel):
    selected_field: str
    confidence: float
    reason: str

class LLMReasoner:
    def __init__(self):
        self.url = f"{settings.OLLAMA_URL}/api/generate"
        self.model = settings.OLLAMA_MODEL

    def ask_mapping(self, vendor: str, device_type: str, field_name: str, field_value: str, context: str, feedback: str = None) -> dict:
        canonical_fields = ", ".join(CANONICAL_FIELDS)

        # Item 5 (agent refine loop): `feedback` carries real information
        # about why a PREVIOUS attempt didn't work (e.g. a canonical field
        # the pipeline still needs is missing), so a refine attempt is a
        # genuinely different prompt, not a blind retry of the same question.
        feedback_block = f"\n\nFeedback from a previous attempt: {feedback}\nReconsider this field with that feedback in mind.\n" if feedback else ""

        prompt = f"""
You are a cybersecurity log parsing expert.
A log from Vendor: {vendor}, Device: {device_type} has an unknown field.
Field Name: "{field_name}"
Example Value: "{field_value}"
Context in log: "{context}"
{feedback_block}
Your task is to map this field to exactly ONE of the following canonical fields:
[{canonical_fields}]

You MUST return ONLY a valid JSON object with exactly these keys:
"selected_field": (the chosen canonical field exactly as written in the list above)
"confidence": (a float between 0.0 and 1.0)
"reason": (a short explanation why)

Do not include markdown blocks, do not include any other text, ONLY the JSON object.
"""
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        try:
            resp = requests.post(self.url, json=payload, timeout=settings.OLLAMA_TIMEOUT_SECONDS)
            resp.raise_for_status()
            data = resp.json()
            response_text = data.get("response", "")
            
            # Parse the constrained output
            parsed = json.loads(response_text)
            
            # Validate output matches schema
            validated = LLMMappingResponse(**parsed)
            
            # Ensure it didn't invent a field
            if validated.selected_field not in CANONICAL_FIELDS:
                raise ValueError("LLM invented a non-canonical field.")
                
            return validated.model_dump()
            
        except Exception as e:
            # Fallback if LLM fails or format is bad
            print(f"LLM Mapping failed: {e}")
            return {
                "selected_field": "UNKNOWN",
                "confidence": 0.0,
                "reason": f"LLM failure: {e}"
            }

llm_reasoner = LLMReasoner()
