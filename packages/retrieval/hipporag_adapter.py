from dataclasses import dataclass

import igraph as ig
import numpy as np

from packages.contracts.graph import FactRecord


@dataclass
class PassageRankingResult:
    chunk_scores: dict[str, float]


@dataclass
class GraphArtifacts:
    graph: ig.Graph
    node_name_to_vertex_idx: dict[str, int]
    entity_to_chunk_ids: dict[str, set[str]]
    passage_ids: list[str]


class HippoRAGRetrievalAdapter:
    @staticmethod
    def _entity_key(title: str, fallback_id: str) -> str:
        normalized = title.strip().lower()
        return normalized or fallback_id

    @staticmethod
    def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
        arr1 = np.array(v1, dtype=np.float32)
        arr2 = np.array(v2, dtype=np.float32)
        denom = np.linalg.norm(arr1) * np.linalg.norm(arr2)
        if denom == 0:
            return 0.0
        return float(np.dot(arr1, arr2) / denom)

    def build_graph_artifacts(
        self,
        facts: list[FactRecord],
        entity_embeddings: dict[str, list[float]] | None = None,
        synonymy_threshold: float = 0.88,
    ) -> GraphArtifacts:
        entity_to_chunk_ids: dict[str, set[str]] = {}
        passage_ids: list[str] = []
        seen_passages: set[str] = set()
        node_to_node_stats: dict[tuple[str, str], float] = {}

        entity_titles_by_key: dict[str, str] = {}
        for fact in facts:
            source_key = self._entity_key(fact.source_title, fact.source_node_id)
            target_key = self._entity_key(fact.target_title, fact.target_node_id)
            entity_titles_by_key[source_key] = fact.source_title or source_key
            entity_titles_by_key[target_key] = fact.target_title or target_key

            node_to_node_stats[(source_key, target_key)] = node_to_node_stats.get((source_key, target_key), 0.0) + 1.0
            node_to_node_stats[(target_key, source_key)] = node_to_node_stats.get((target_key, source_key), 0.0) + 1.0

            for chunk_id in fact.chunk_ids:
                entity_to_chunk_ids.setdefault(source_key, set()).add(chunk_id)
                entity_to_chunk_ids.setdefault(target_key, set()).add(chunk_id)
                node_to_node_stats[(chunk_id, source_key)] = 1.0
                node_to_node_stats[(chunk_id, target_key)] = 1.0
                if chunk_id not in seen_passages:
                    seen_passages.add(chunk_id)
                    passage_ids.append(chunk_id)

        if entity_embeddings:
            entity_keys = list(entity_titles_by_key.keys())
            for idx, source_key in enumerate(entity_keys):
                source_embedding = entity_embeddings.get(source_key)
                if source_embedding is None:
                    continue
                for target_key in entity_keys[idx + 1:]:
                    target_embedding = entity_embeddings.get(target_key)
                    if target_embedding is None:
                        continue
                    similarity = self._cosine_similarity(source_embedding, target_embedding)
                    if similarity < synonymy_threshold:
                        continue
                    node_to_node_stats[(source_key, target_key)] = max(node_to_node_stats.get((source_key, target_key), 0.0), similarity)
                    node_to_node_stats[(target_key, source_key)] = max(node_to_node_stats.get((target_key, source_key), 0.0), similarity)

        node_names = sorted({name for edge in node_to_node_stats for name in edge})
        node_name_to_vertex_idx = {name: idx for idx, name in enumerate(node_names)}
        edges: list[tuple[int, int]] = []
        edge_weights: list[float] = []
        for (src, dst), weight in node_to_node_stats.items():
            edges.append((node_name_to_vertex_idx[src], node_name_to_vertex_idx[dst]))
            edge_weights.append(weight)

        graph = ig.Graph(n=len(node_names), edges=edges, directed=False)
        graph.vs["name"] = node_names
        graph.es["weight"] = edge_weights if edge_weights else []
        return GraphArtifacts(
            graph=graph,
            node_name_to_vertex_idx=node_name_to_vertex_idx,
            entity_to_chunk_ids=entity_to_chunk_ids,
            passage_ids=passage_ids,
        )

    def rank_passages_with_ppr(
        self,
        facts: list[FactRecord],
        fused_fact_ids: list[str],
        dense_fact_score_by_id: dict[str, float],
        dense_passage_prior: dict[str, float],
        graph_artifacts: GraphArtifacts,
        damping: float = 0.85,
        passage_node_weight: float = 0.2,
    ) -> PassageRankingResult:
        fact_by_id = {fact.fact_id: fact for fact in facts}
        node_name_to_vertex_idx = graph_artifacts.node_name_to_vertex_idx
        entity_to_chunk_ids = graph_artifacts.entity_to_chunk_ids
        passage_ids = graph_artifacts.passage_ids
        graph = graph_artifacts.graph
        if not node_name_to_vertex_idx:
            return PassageRankingResult(chunk_scores={})

        phrase_weights = np.zeros(len(node_name_to_vertex_idx), dtype=np.float32)
        passage_weights = np.zeros(len(node_name_to_vertex_idx), dtype=np.float32)
        number_of_occurs = np.zeros(len(node_name_to_vertex_idx), dtype=np.float32)

        for rank, fact_id in enumerate(fused_fact_ids, start=1):
            fact = fact_by_id.get(fact_id)
            if fact is None:
                continue
            fact_score = dense_fact_score_by_id.get(fact_id, 0.0) + (1.0 / (60 + rank))
            for phrase_key in [
                self._entity_key(fact.source_title, fact.source_node_id),
                self._entity_key(fact.target_title, fact.target_node_id),
            ]:
                phrase_id = node_name_to_vertex_idx.get(phrase_key)
                if phrase_id is None:
                    continue
                weighted_fact_score = fact_score
                linked_chunks = entity_to_chunk_ids.get(phrase_key, set())
                if linked_chunks:
                    weighted_fact_score /= len(linked_chunks)
                phrase_weights[phrase_id] += weighted_fact_score
                number_of_occurs[phrase_id] += 1

        valid_phrase_mask = number_of_occurs > 0
        phrase_weights[valid_phrase_mask] = phrase_weights[valid_phrase_mask] / number_of_occurs[valid_phrase_mask]

        for chunk_id, prior_score in dense_passage_prior.items():
            passage_id = node_name_to_vertex_idx.get(chunk_id)
            if passage_id is not None:
                passage_weights[passage_id] = prior_score * passage_node_weight

        node_weights = phrase_weights + passage_weights
        if float(node_weights.sum()) <= 0:
            return PassageRankingResult(chunk_scores={})

        pagerank_scores = graph.personalized_pagerank(
            vertices=range(len(node_name_to_vertex_idx)),
            damping=damping,
            directed=False,
            weights="weight",
            reset=node_weights.tolist(),
            implementation="prpack",
        )

        chunk_scores = {
            chunk_id: float(pagerank_scores[node_name_to_vertex_idx[chunk_id]])
            for chunk_id in passage_ids
            if chunk_id in node_name_to_vertex_idx
        }
        return PassageRankingResult(chunk_scores=chunk_scores)
