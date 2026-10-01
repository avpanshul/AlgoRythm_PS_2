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
        self.ollama_url = f"{settings.OLLAMA_URL}/api/generate"
        self.ollama_model = settings.OLLAMA_MODEL
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.groq_model = settings.GROQ_MODEL

    def _build_prompt(self, vendor: str, device_type: str, field_name: str, field_value: str, context: str, feedback: str) -> tuple[str, str]:
        canonical_fields = ", ".join(CANONICAL_FIELDS)

        # Item 5 (agent refine loop): `feedback` carries real information
        # about why a PREVIOUS attempt didn't work (e.g. a canonical field
        # the pipeline still needs is missing), so a refine attempt is a
        # genuinely different prompt, not a blind retry of the same question.
        feedback_block = f"\n\nFeedback from a previous attempt: {feedback}\nReconsider this field with that feedback in mind.\n" if feedback else ""

        system = "You are a cybersecurity log parsing expert. You MUST return ONLY a valid JSON object, no markdown, no other text."
        user = f"""A log from Vendor: {vendor}, Device: {device_type} has an unknown field.
Field Name: "{field_name}"
Example Value: "{field_value}"
Context in log: "{context}"
{feedback_block}
Your task is to map this field to exactly ONE of the following canonical fields:
[{canonical_fields}]

Return a JSON object with exactly these keys:
"selected_field": (the chosen canonical field exactly as written in the list above)
"confidence": (a float between 0.0 and 1.0)
"reason": (a short explanation why)"""
        return system, user

    def _validate(self, response_text: str) -> dict:
        parsed = json.loads(response_text)
        validated = LLMMappingResponse(**parsed)
        # Ensure it didn't invent a field
        if validated.selected_field not in CANONICAL_FIELDS:
            raise ValueError("LLM invented a non-canonical field.")
        return validated.model_dump()

    def _ask_groq(self, system: str, user: str) -> dict:
        resp = requests.post(
            self.groq_url,
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": self.groq_model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            },
            timeout=settings.GROQ_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        response_text = data["choices"][0]["message"]["content"]
        return self._validate(response_text)

    def _ask_ollama(self, system: str, user: str) -> dict:
        resp = requests.post(
            self.ollama_url,
            json={"model": self.ollama_model, "prompt": f"{system}\n\n{user}", "stream": False, "format": "json"},
            timeout=settings.OLLAMA_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        response_text = data.get("response", "")
        return self._validate(response_text)

    def ask_mapping(self, vendor: str, device_type: str, field_name: str, field_value: str, context: str, feedback: str = None) -> dict:
        system, user = self._build_prompt(vendor, device_type, field_name, field_value, context, feedback)
        try:
            # Real hosted API takes priority when configured (GROQ_API_KEY
            # set) -- same shape of HTTP call this code already made, just
            # pointed at an endpoint that actually exists. Falls back to
            # Ollama (the original behavior, for real local installs) when
            # no key is set, so this is purely additive, never a regression
            # for anyone already running a local Ollama server.
            #
            # AIRGAPPED_MODE check: Groq is a real external cloud API --
            # inherently incompatible with an air-gapped install by
            # definition, unlike OLLAMA_URL, which in a real docker-compose
            # deployment points at the `ollama` container on the same
            # internal network (never leaves the air-gapped boundary). A
            # genuinely air-gapped deployment should keep using local Ollama
            # even if a GROQ_API_KEY happens to be set (e.g. leftover from a
            # non-air-gapped config), not silently reach out to the internet.
            if settings.GROQ_API_KEY and not settings.AIRGAPPED_MODE:
                return self._ask_groq(system, user)
            return self._ask_ollama(system, user)
        except Exception as e:
            # Fallback if LLM fails or format is bad
            print(f"LLM Mapping failed: {e}")
            return {
                "selected_field": "UNKNOWN",
                "confidence": 0.0,
                "reason": f"LLM failure: {e}"
            }

llm_reasoner = LLMReasoner()
