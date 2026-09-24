from sentence_transformers import SentenceTransformer
from scipy.spatial.distance import cosine
from app.core.config import settings

class EmbeddingEngine:
    def __init__(self):
        # This will download the model locally on first run if not present
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        
        # Canonical vocabulary to map against
        self.canonical_fields = [
            "source.ip",
            "source.port",
            "destination.ip",
            "destination.port",
            "event.action",
            "event.category",
            "event.type",
            "event.severity",
            "event.outcome",
            "network.protocol",
            "network.transport",
            "user.name",
            "device.id",
            "device.vendor",
            "device.product",
            "timestamp"
        ]
        
        # Pre-compute embeddings for canonical fields
        self.canonical_embeddings = {
            field: self.model.encode(field) for field in self.canonical_fields
        }

    def find_best_mapping(self, unknown_field: str) -> dict:
        unknown_emb = self.model.encode(unknown_field)
        
        best_field = None
        best_score = -1
        
        for can_field, can_emb in self.canonical_embeddings.items():
            # cosine distance is 0 for identical, 1 for orthogonal
            # similarity is 1 - distance
            sim = 1 - cosine(unknown_emb, can_emb)
            if sim > best_score:
                best_score = sim
                best_field = can_field
                
        return {
            "input_field": unknown_field,
            "candidate": best_field,
            "similarity": float(best_score),
            "confidence": float(best_score)
        }

embedding_engine = EmbeddingEngine()
