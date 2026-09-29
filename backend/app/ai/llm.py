import json
import requests
from pydantic import BaseModel
from app.core.config import settings
from app.ai.embeddings import embedding_engine

class LLMMappingResponse(BaseModel):
    selected_field: str
    confidence: float
    reason: str

class LLMReasoner:
    def __init__(self):
        self.url = f"{settings.OLLAMA_URL}/api/generate"
        self.model = settings.OLLAMA_MODEL

    def ask_mapping(self, vendor: str, device_type: str, field_name: str, field_value: str, context: str, feedback: str = None) -> dict:
        canonical_fields = ", ".join(embedding_engine.canonical_fields)

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
            if validated.selected_field not in embedding_engine.canonical_fields:
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
