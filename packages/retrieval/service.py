import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import faiss
import jieba
import numpy as np

from packages.contracts.retrieval import RetrievalRequest, RetrievalResult, RetrievedPassage
from packages.contracts.graph import FactRecord, GraphDelta, EvidenceItem
from packages.common.config import model_config
from packages.embedding.aliyun_client import AliyunEmbeddingClient
from packages.embedding.bge_local_client import BGELocalEmbeddingClient
from packages.retrieval.hipporag_adapter import HippoRAGRetrievalAdapter


class RetrievalService(Protocol):
    def retrieve_for_query(self, req: RetrievalRequest) -> RetrievalResult: ...

    def retrieve_for_node(self, graph_id: str, node_id: str, query: str) -> RetrievalResult: ...

    def update_index(self, graph_id: str, delta: GraphDelta) -> None: ...


@dataclass
class ChunkRow:
    chunk_id: str
    document_id: str
    content: str
    graph_id: str | None = None


class LocalEmbeddingRetrievalService:
    def __init__(
        self,
        chunk_file_path: str | None = None,
        embedding_cache_file_path: str | None = None,
        documents_file_path: str | None = None,
        facts_file_path: str | None = None,
        fact_embedding_cache_file_path: str | None = None,
        embed_client: object | None = None,
    ) -> None:
        data_root = Path(__file__).resolve().parents[2] / "data"
        if chunk_file_path is None:
            chunk_file_path = str(data_root / "dynamic_chunks.json")
        if embedding_cache_file_path is None:
            embedding_cache_file_path = str(data_root / "chunk_embeddings.json")
        if documents_file_path is None:
            documents_file_path = str(data_root / "documents.json")
        if facts_file_path is None:
            facts_file_path = str(data_root / "facts.json")
        if fact_embedding_cache_file_path is None:
            fact_embedding_cache_file_path = str(data_root / "fact_embeddings.json")
        self.entity_embedding_cache_file_path = str(data_root / "entity_embeddings.json")

        self.chunk_file_path = chunk_file_path
        self.embedding_cache_file_path = embedding_cache_file_path
        self.documents_file_path = documents_file_path
        self.facts_file_path = facts_file_path
        self.fact_embedding_cache_file_path = fact_embedding_cache_file_path
        if embed_client is not None:
            self.embed_client = embed_client
        elif model_config.embedding_provider == "local_bge":
            self.embed_client = BGELocalEmbeddingClient(model_path=model_config.embedding_local_model_path)
        else:
            self.embed_client = AliyunEmbeddingClient()
        self.hipporag_adapter = HippoRAGRetrievalAdapter()
        self._graph_cache: dict[str, tuple[tuple[int, int], object]] = {}

    def _load_chunks(self) -> list[ChunkRow]:
        if not Path(self.chunk_file_path).exists():
            return []
        with open(self.chunk_file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [
            ChunkRow(
                chunk_id=item["chunk_id"],
                document_id=item.get("document_id", ""),
                content=item["content"],
                graph_id=item.get("graph_id"),
            )
            for item in raw
        ]

    def _load_facts(self) -> list[FactRecord]:
        path = Path(self.facts_file_path)
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)
        return [FactRecord(**row) for row in rows]

    def _filter_facts_for_graph(self, facts: list[FactRecord], graph_id: str) -> list[FactRecord]:
        return [fact for fact in facts if fact.graph_id == graph_id]

    def _load_document_graph_map(self) -> dict[str, str]:
        path = Path(self.documents_file_path)
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)
        return {row.get("document_id", ""): row.get("graph_id", "") for row in rows}

    def _filter_chunks_for_graph(self, chunks: list[ChunkRow], graph_id: str) -> list[ChunkRow]:
        doc_graph_map = self._load_document_graph_map()
        filtered: list[ChunkRow] = []
        for chunk in chunks:
            chunk_graph_id = chunk.graph_id
            if not chunk_graph_id and chunk.document_id.startswith("graph_"):
                chunk_graph_id = chunk.document_id[len("graph_"):]
            if not chunk_graph_id:
                chunk_graph_id = doc_graph_map.get(chunk.document_id)
            if chunk_graph_id == graph_id:
                filtered.append(chunk)
        return filtered

    @staticmethod
    def _load_json_dict(path_str: str) -> dict[str, list[float]]:
        path = Path(path_str)
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _save_json_dict(path_str: str, rows: dict[str, list[float]]) -> None:
        with open(path_str, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        normalized = text.lower().strip()
        if not normalized:
            return []
        zh_tokens = [token.strip() for token in jieba.cut_for_search(normalized) if token.strip()]
        en_tokens = re.findall(r"[a-z0-9_./+-]+", normalized)
        return zh_tokens + en_tokens

    def _get_cached_embedding(
        self,
        cache: dict[str, list[float]],
        cache_key: str,
        text: str,
        expected_dim: int | None = None,
    ) -> list[float]:
        cached = cache.get(cache_key)
        if cached is not None and (expected_dim is None or len(cached) == expected_dim):
            return cached
        emb = self.embed_client.embed(text)
        cache[cache_key] = emb
        return emb

    def precompute_embeddings(self, graph_id: str, chunk_ids: list[str] | None = None) -> int:
        chunks = self._filter_chunks_for_graph(self._load_chunks(), graph_id=graph_id)
        if chunk_ids is not None:
            chunk_id_set = set(chunk_ids)
            chunks = [chunk for chunk in chunks if chunk.chunk_id in chunk_id_set]
        if not chunks:
            return 0

        cache = self._load_json_dict(self.embedding_cache_file_path)
        probe = self.embed_client.embed("embedding dimension probe")
        expected_dim = len(probe)
        computed = 0
        for chunk in chunks:
            cached = cache.get(chunk.chunk_id)
            if cached is not None and len(cached) == expected_dim:
                continue
            cache[chunk.chunk_id] = self.embed_client.embed(chunk.content)
            computed += 1
        self._save_json_dict(self.embedding_cache_file_path, cache)
        return computed

    def precompute_fact_embeddings(self, graph_id: str) -> int:
        facts = self._filter_facts_for_graph(self._load_facts(), graph_id=graph_id)
        if not facts:
            return 0

        cache = self._load_json_dict(self.fact_embedding_cache_file_path)
        probe = self.embed_client.embed("fact embedding dimension probe")
        expected_dim = len(probe)
        computed = 0
        for fact in facts:
            cached = cache.get(fact.fact_id)
            if cached is not None and len(cached) == expected_dim:
                continue
            cache[fact.fact_id] = self.embed_client.embed(fact.fact_text)
            computed += 1
        self._save_json_dict(self.fact_embedding_cache_file_path, cache)
        return computed

    def _compute_entity_embeddings(self, facts: list[FactRecord]) -> dict[str, list[float]]:
        cache = self._load_json_dict(self.entity_embedding_cache_file_path)
        probe = self.embed_client.embed("entity embedding dimension probe")
        expected_dim = len(probe)
        entity_text_by_key: dict[str, str] = {}
        for fact in facts:
            source_key = (fact.source_title or fact.source_node_id).strip().lower() or fact.source_node_id
            target_key = (fact.target_title or fact.target_node_id).strip().lower() or fact.target_node_id
            entity_text_by_key[source_key] = fact.source_title or fact.source_node_id
            entity_text_by_key[target_key] = fact.target_title or fact.target_node_id

        result: dict[str, list[float]] = {}
        for entity_key, entity_text in entity_text_by_key.items():
            cached = cache.get(entity_key)
            if cached is None or len(cached) != expected_dim:
                cached = self.embed_client.embed(entity_text)
                cache[entity_key] = cached
            result[entity_key] = cached

        self._save_json_dict(self.entity_embedding_cache_file_path, cache)
        return result

    def _get_graph_artifacts(self, graph_id: str, facts: list[FactRecord], entity_embeddings: dict[str, list[float]]):
        cache_key = (len(facts), sum(len(fact.chunk_ids) for fact in facts))
        cached = self._graph_cache.get(graph_id)
        if cached is not None and cached[0] == cache_key:
            return cached[1]

        artifacts = self.hipporag_adapter.build_graph_artifacts(
            facts=facts,
            entity_embeddings=entity_embeddings,
        )
        self._graph_cache[graph_id] = (cache_key, artifacts)
        return artifacts

    def _build_hnsw_index(self, vectors: np.ndarray) -> faiss.IndexHNSWFlat:
        dim = vectors.shape[1]
        index = faiss.IndexHNSWFlat(dim, 32, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = 200
        index.hnsw.efSearch = 64
        index.add(vectors)
        return index

    def _ann_rank_texts(self, items: list[tuple[str, str]], query: str, cache_path: str) -> list[tuple[str, float]]:
        if not items:
            return []
        cache = self._load_json_dict(cache_path)
        query_embedding = self.embed_client.embed(query)
        expected_dim = len(query_embedding)
        item_ids: list[str] = []
        vectors: list[list[float]] = []
        for item_id, text in items:
            emb = self._get_cached_embedding(cache=cache, cache_key=item_id, text=text, expected_dim=expected_dim)
            item_ids.append(item_id)
            vectors.append(emb)
        self._save_json_dict(cache_path, cache)

        matrix = np.array(vectors, dtype=np.float32)
        query_vector = np.array([query_embedding], dtype=np.float32)
        index = self._build_hnsw_index(matrix)
        k = min(max(1, len(item_ids)), 50)
        scores, ids = index.search(query_vector, k)
        ranking: list[tuple[str, float]] = []
        for score, idx in zip(scores[0], ids[0]):
            if idx < 0:
                continue
            ranking.append((item_ids[int(idx)], float(score)))
        return ranking

    def _bm25_rank_texts(self, items: list[tuple[str, str]], query: str) -> list[tuple[str, float]]:
        if not items:
            return []
        tokenized_docs = [self._tokenize(text) for _, text in items]
        avgdl = sum(len(tokens) for tokens in tokenized_docs) / max(1, len(tokenized_docs))
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        doc_freq: dict[str, int] = {}
        for tokens in tokenized_docs:
            for token in set(tokens):
                doc_freq[token] = doc_freq.get(token, 0) + 1

        k1 = 1.5
        b = 0.75
        n_docs = len(items)
        results: list[tuple[str, float]] = []
        for (item_id, _), tokens in zip(items, tokenized_docs):
            score = 0.0
            doc_len = len(tokens)
            tf_map: dict[str, int] = {}
            for token in tokens:
                tf_map[token] = tf_map.get(token, 0) + 1
            for token in query_tokens:
                tf = tf_map.get(token, 0)
                if tf == 0:
                    continue
                df = doc_freq.get(token, 0)
                idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
                score += idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / max(1.0, avgdl))))
            if score > 0:
                results.append((item_id, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    @staticmethod
    def _rrf_fusion(*rankings: list[tuple[str, float]], k: int = 60) -> list[str]:
        total: dict[str, float] = {}
        for ranking in rankings:
            for idx, (item_id, _) in enumerate(ranking, start=1):
                total[item_id] = total.get(item_id, 0.0) + (1.0 / (k + idx))
        return [item_id for item_id, _ in sorted(total.items(), key=lambda x: x[1], reverse=True)]

    def _chunk_dense_prior(self, chunks: list[ChunkRow], query: str) -> dict[str, float]:
        if not chunks:
            return {}
        chunk_items = [(chunk.chunk_id, chunk.content) for chunk in chunks[:300]]
        dense_ranking = self._ann_rank_texts(chunk_items, query, self.embedding_cache_file_path)
        if not dense_ranking:
            return {}
        scores = np.array([score for _, score in dense_ranking], dtype=np.float32)
        if scores.max() == scores.min():
            normalized = np.ones_like(scores)
        else:
            normalized = (scores - scores.min()) / (scores.max() - scores.min())
        return {chunk_id: float(score) for (chunk_id, _), score in zip(dense_ranking, normalized)}

    def _rerank_facts(
        self,
        query: str,
        facts: list[FactRecord],
        fused_fact_ids: list[str],
        dense_fact_score_by_id: dict[str, float],
        limit: int,
    ) -> list[str]:
        if not fused_fact_ids:
            return []

        query_tokens = set(self._tokenize(query))
        scored_ids: list[tuple[str, float]] = []
        fact_by_id = {fact.fact_id: fact for fact in facts}
        for rank, fact_id in enumerate(fused_fact_ids, start=1):
            fact = fact_by_id.get(fact_id)
            if fact is None:
                continue
            fact_tokens = set(self._tokenize(fact.fact_text))
            lexical_overlap = len(query_tokens.intersection(fact_tokens))
            relation_bonus = 0.0
            relation_text = fact.relation_type.lower()
            if relation_text and relation_text in query.lower():
                relation_bonus = 1.0
            score = dense_fact_score_by_id.get(fact_id, 0.0) + (0.1 * lexical_overlap) + relation_bonus + (1.0 / (60 + rank))
            scored_ids.append((fact_id, score))

        scored_ids.sort(key=lambda x: x[1], reverse=True)
        return [fact_id for fact_id, _ in scored_ids[:limit]]

    def _chunk_first_retrieve(self, req: RetrievalRequest) -> RetrievalResult:
        chunks = self._filter_chunks_for_graph(self._load_chunks(), graph_id=req.graph_id)
        if not chunks:
            return RetrievalResult(passages=[], evidence=[], retrieved_passages=[])
        chunk_items = [(chunk.chunk_id, chunk.content) for chunk in chunks[:300]]
        dense_ranking = self._ann_rank_texts(chunk_items, req.query, self.embedding_cache_file_path)
        sparse_ranking = self._bm25_rank_texts(chunk_items, req.query)
        fused_ids = self._rrf_fusion(dense_ranking, sparse_ranking)
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        dense_score_by_id = dict(dense_ranking)
        top_ids = [chunk_id for chunk_id in fused_ids if chunk_id in chunk_by_id][: max(1, min(req.top_k, len(fused_ids)))]
        retrieved_passages = [
            RetrievedPassage(chunk_id=chunk_id, content=chunk_by_id[chunk_id].content, score=float(dense_score_by_id.get(chunk_id, 0.0)))
            for chunk_id in top_ids
        ]
        evidence = [EvidenceItem(evidence_id=f"ev_{item.chunk_id}", chunk_id=item.chunk_id, score=item.score) for item in retrieved_passages]
        return RetrievalResult(passages=[item.content for item in retrieved_passages], evidence=evidence, retrieved_passages=retrieved_passages)

    def _fact_first_retrieve(self, req: RetrievalRequest) -> RetrievalResult:
        facts = self._filter_facts_for_graph(self._load_facts(), graph_id=req.graph_id)
        if not facts:
            return self._chunk_first_retrieve(req)

        self.precompute_fact_embeddings(graph_id=req.graph_id)
        chunks = self._filter_chunks_for_graph(self._load_chunks(), graph_id=req.graph_id)
        if not chunks:
            return RetrievalResult(passages=[], evidence=[], retrieved_passages=[])

        fact_items = [(fact.fact_id, fact.fact_text) for fact in facts]
        dense_fact_ranking = self._ann_rank_texts(fact_items, req.query, self.fact_embedding_cache_file_path)
        sparse_fact_ranking = self._bm25_rank_texts(fact_items, req.query)
        fused_fact_ids = self._rrf_fusion(dense_fact_ranking, sparse_fact_ranking)[: max(req.top_k * 5, 12)]
        dense_fact_score_by_id = dict(dense_fact_ranking)
        reranked_fact_ids = self._rerank_facts(
            query=req.query,
            facts=facts,
            fused_fact_ids=fused_fact_ids,
            dense_fact_score_by_id=dense_fact_score_by_id,
            limit=max(req.top_k * 3, 8),
        )
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        dense_passage_prior = self._chunk_dense_prior(chunks, req.query)
        entity_embeddings = self._compute_entity_embeddings(facts)
        graph_artifacts = self._get_graph_artifacts(req.graph_id, facts, entity_embeddings)
        chunk_scores = self.hipporag_adapter.rank_passages_with_ppr(
            facts=facts,
            fused_fact_ids=reranked_fact_ids,
            dense_fact_score_by_id=dense_fact_score_by_id,
            dense_passage_prior=dense_passage_prior,
            graph_artifacts=graph_artifacts,
        ).chunk_scores

        ranked_chunk_ids = [chunk_id for chunk_id, _ in sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)]
        top_ids = [chunk_id for chunk_id in ranked_chunk_ids if chunk_id in chunk_by_id][: max(1, min(req.top_k, len(ranked_chunk_ids)))]
        if not top_ids:
            return self._chunk_first_retrieve(req)

        retrieved_passages = [
            RetrievedPassage(chunk_id=chunk_id, content=chunk_by_id[chunk_id].content, score=float(chunk_scores.get(chunk_id, 0.0)))
            for chunk_id in top_ids
        ]
        evidence = [EvidenceItem(evidence_id=f"ev_{item.chunk_id}", chunk_id=item.chunk_id, score=item.score) for item in retrieved_passages]
        return RetrievalResult(passages=[item.content for item in retrieved_passages], evidence=evidence, retrieved_passages=retrieved_passages)

    def retrieve_for_query(self, req: RetrievalRequest) -> RetrievalResult:
        return self._fact_first_retrieve(req)

    def retrieve_for_node(self, graph_id: str, node_id: str, query: str) -> RetrievalResult:
        return self.retrieve_for_query(RetrievalRequest(graph_id=graph_id, query=query, top_k=5))

    def update_index(self, graph_id: str, delta: GraphDelta) -> None:
        return None
