import json
import re

from packages.common.config import model_config
from packages.embedding.aliyun_client import AliyunEmbeddingClient
from packages.embedding.bge_local_client import BGELocalEmbeddingClient
from packages.llm.deepseek_client import DeepSeekClient


DEFAULT_ALIASES = {
    "rnns": "recurrent neural networks",
    "rnn": "recurrent neural networks",
    "attention mechanisms": "attention mechanism",
    "transformers": "transformer",
    "multihead attention": "multi-head attention",
    "multi head attention": "multi-head attention",
}


class EntityResolutionService:
    def __init__(self) -> None:
        if model_config.embedding_provider == "local_bge":
            self.embed_client = BGELocalEmbeddingClient(model_path=model_config.embedding_local_model_path)
        else:
            self.embed_client = AliyunEmbeddingClient()
        self.llm_client = DeepSeekClient()
        self.aliases = DEFAULT_ALIASES
        self._embedding_cache: dict[str, list[float]] = {}
        self._type_cache: dict[str, str] = {}

    def normalize_entity_name(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        normalized = re.sub(r"^[^a-z0-9一-鿿]+|[^a-z0-9一-鿿]+$", "", normalized)
        normalized = self.aliases.get(normalized, normalized)
        return normalized

    def retrieve_entity_candidates(self, normalized_name: str, existing_entities: dict[str, dict], top_k: int = 5) -> list[dict]:
        if not existing_entities:
            return []
        query_embedding = self._embed(normalized_name)
        scored = []
        for key, entity in existing_entities.items():
            entity_embedding = entity.get("embedding") or self._embed(key)
            score = self._cosine_similarity(query_embedding, entity_embedding)
            scored.append((score, entity))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entity | {"similarity": score} for score, entity in scored[:top_k]]

    def match_by_attributes(self, entity_name: str, candidate: dict, neighbors: set[str]) -> bool:
        if candidate.get("normalized_name") == entity_name:
            return True
        candidate_neighbors = set(candidate.get("neighbors", []))
        if neighbors and candidate_neighbors and len(neighbors.intersection(candidate_neighbors)) > 0:
            return True
        return False

    def llm_entity_judge(self, entity_name: str, candidate: dict, context: str) -> bool:
        prompt = (
            "Decide whether two entity mentions in a study-note graph refer to the same learning concept. "
            "Be conservative. Respond with JSON only: {\"same_entity\": true|false}.\n\n"
            f"New entity: {entity_name}\n"
            f"Candidate entity: {candidate.get('title', '')}\n"
            f"Candidate normalized form: {candidate.get('normalized_name', '')}\n"
            f"Candidate neighbors: {candidate.get('neighbors', [])}\n"
            f"Context: {context[:500]}"
        )
        try:
            response = self.llm_client.chat(prompt)
            data = json.loads(response)
            return bool(data.get("same_entity", False))
        except Exception:
            return False

    def resolve_entity(self, title: str, context: str, existing_entities: dict[str, dict], neighbors: set[str]) -> dict:
        normalized_name = self.normalize_entity_name(title)
        if not normalized_name:
            return {"action": "drop"}
        candidates = self.retrieve_entity_candidates(normalized_name, existing_entities)
        for candidate in candidates:
            if candidate.get("similarity", 0.0) >= 0.97:
                return {"action": "merge", "normalized_name": candidate["normalized_name"]}
            if candidate.get("similarity", 0.0) >= 0.88 and self.match_by_attributes(normalized_name, candidate, neighbors):
                return {"action": "merge", "normalized_name": candidate["normalized_name"]}
            if candidate.get("similarity", 0.0) >= 0.88 and self.llm_entity_judge(normalized_name, candidate, context):
                return {"action": "merge", "normalized_name": candidate["normalized_name"]}
            if candidate.get("similarity", 0.0) >= 0.78:
                return {
                    "action": "synonymy",
                    "normalized_name": normalized_name,
                    "canonical_name": candidate["normalized_name"],
                }
        return {"action": "new", "normalized_name": normalized_name}

    def classify_entity_type(self, title: str, context: str) -> str:
        key = f"{title}::{context[:160]}"
        cached = self._type_cache.get(key)
        if cached is not None:
            return cached
        prompt = (
            "Classify the graph node into one of these types only: "
            "Concept, Method, Metric, Result, Question, Insight, Component. "
            "Return JSON only: {\"node_type\": \"Concept\"}.\n\n"
            f"Node title: {title}\n"
            f"Context: {context[:600]}"
        )
        try:
            response = self.llm_client.chat(prompt)
            data = json.loads(response)
            node_type = str(data.get('node_type', 'Concept')).strip() or 'Concept'
        except Exception:
            node_type = 'Concept'
        self._type_cache[key] = node_type
        return node_type

    def _embed(self, text: str) -> list[float]:
        cached = self._embedding_cache.get(text)
        if cached is not None:
            return cached
        emb = self.embed_client.embed(text)
        self._embedding_cache[text] = emb
        return emb

    @staticmethod
    def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
        num = sum(a * b for a, b in zip(v1, v2))
        denom1 = sum(a * a for a in v1) ** 0.5
        denom2 = sum(b * b for b in v2) ** 0.5
        if denom1 == 0 or denom2 == 0:
            return 0.0
        return num / (denom1 * denom2)
