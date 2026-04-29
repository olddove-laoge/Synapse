import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Literal
from uuid import uuid4

from pydantic import BaseModel

from packages.common.config import app_config
from packages.contracts.graph import FactRecord, FocusGraphResponse, GraphDelta, GraphEdge, GraphNode, PublishCandidatesResponse, PublishSkippedItem
from packages.graph.neo4j_store import Neo4jGraphStore
from packages.llm.deepseek_client import DeepSeekClient
from packages.retrieval.service import LocalEmbeddingRetrievalService


class ReviewResult(BaseModel):
    graph_id: str
    action: Literal["approve", "reject"]
    candidate_ids: list[str]


class CandidateDeltaRecord(BaseModel):
    candidate_delta_id: str
    graph_id: str
    status: Literal["draft", "reviewed", "rejected", "published"]
    delta: GraphDelta
    created_at: str
    updated_at: str
    source: str = "chat"


class PublishResult(PublishCandidatesResponse):
    pass


class GraphService(Protocol):
    def apply_delta(self, graph_id: str, delta: GraphDelta, source: str = "chat") -> str: ...

    def focus_view(self, graph_id: str, node_id: str) -> FocusGraphResponse: ...

    def graph_view(self, graph_id: str) -> FocusGraphResponse: ...

    def summarize_node(self, graph_id: str, node_id: str) -> GraphNode: ...

    def create_manual_node(self, graph_id: str, node_id: str, title: str, node_type: str, summary: str = "") -> str: ...

    def create_manual_edge(self, graph_id: str, edge_id: str, source_node_id: str, target_node_id: str, relation_type: str) -> str: ...

    def clear_graph(self, graph_id: str) -> None: ...

    def review_candidates(self, graph_id: str, ids: list[str], action: str) -> ReviewResult: ...

    def publish_candidates(self, graph_id: str, ids: list[str]) -> PublishResult: ...

    def list_candidates(self, graph_id: str, status: str | None = None) -> list[CandidateDeltaRecord]: ...


class LocalGraphService:
    def __init__(self, data_root: str | None = None) -> None:
        if data_root is None:
            data_root = str(Path(__file__).resolve().parents[2] / "data")
        self.data_root = Path(data_root)
        self.candidates_file = self.data_root / "candidates.json"
        self.graph_store_file = self.data_root / "graph_store.json"
        self.dynamic_chunks_file = self.data_root / "dynamic_chunks.json"
        self.facts_file = self.data_root / "facts.json"
        self._neo4j_store: Neo4jGraphStore | None = None
        if not self.candidates_file.exists():
            self.candidates_file.write_text("[]", encoding="utf-8")
        if not self.graph_store_file.exists():
            self.graph_store_file.write_text("[]", encoding="utf-8")
        if not self.dynamic_chunks_file.exists():
            self.dynamic_chunks_file.write_text("[]", encoding="utf-8")
        if not self.facts_file.exists():
            self.facts_file.write_text("[]", encoding="utf-8")

    def _get_neo4j_store(self) -> Neo4jGraphStore | None:
        if self._neo4j_store is not None:
            return self._neo4j_store
        try:
            store = Neo4jGraphStore(
                uri=app_config.neo4j_uri,
                user=app_config.neo4j_user,
                password=app_config.neo4j_password,
            )
            store.verify_connection()
            self._neo4j_store = store
            return store
        except Exception:
            return None

    def apply_delta(self, graph_id: str, delta: GraphDelta, source: str = "chat") -> str:
        now = datetime.now(timezone.utc).isoformat()
        candidate_delta_id = f"delta_{uuid4().hex}"
        record = CandidateDeltaRecord(
            candidate_delta_id=candidate_delta_id,
            graph_id=graph_id,
            status="draft",
            delta=delta,
            created_at=now,
            updated_at=now,
            source=source,
        )
        rows = self._load_json(self.candidates_file)
        rows.append(record.model_dump())
        self._save_json(self.candidates_file, rows)
        return candidate_delta_id

    def create_manual_node(self, graph_id: str, node_id: str, title: str, node_type: str, summary: str = "") -> str:
        graph_rows = self._load_json(self.graph_store_file)
        graph_rows.append(
            {
                'graph_id': graph_id,
                'candidate_delta_id': f'manual_{uuid4().hex}',
                'delta': {
                    'nodes': [
                        {
                            'node_id': node_id,
                            'title': title,
                            'node_type': node_type,
                            'summary': summary,
                            'status': 'published',
                        }
                    ],
                    'edges': [],
                    'evidence': [],
                },
                'published_at': datetime.now(timezone.utc).isoformat(),
            }
        )
        self._save_json(self.graph_store_file, graph_rows)
        return node_id

    def create_manual_edge(self, graph_id: str, edge_id: str, source_node_id: str, target_node_id: str, relation_type: str) -> str:
        graph_rows = self._load_json(self.graph_store_file)
        graph_rows.append(
            {
                'graph_id': graph_id,
                'candidate_delta_id': f'manual_{uuid4().hex}',
                'delta': {
                    'nodes': [],
                    'edges': [
                        {
                            'edge_id': edge_id,
                            'source_node_id': source_node_id,
                            'target_node_id': target_node_id,
                            'relation_type': relation_type,
                            'status': 'published',
                        }
                    ],
                    'evidence': [],
                },
                'published_at': datetime.now(timezone.utc).isoformat(),
            }
        )
        self._save_json(self.graph_store_file, graph_rows)
        return edge_id

    def graph_view(self, graph_id: str) -> FocusGraphResponse:
        graph_rows = self._load_json(self.graph_store_file)
        node_map: dict[str, dict] = {}
        edge_map: dict[str, dict] = {}
        for row in graph_rows:
            if row.get("graph_id") != graph_id:
                continue
            delta = row.get("delta", {})
            for node in delta.get("nodes", []):
                node_map[node["node_id"]] = {
                    "node_id": node["node_id"],
                    "title": node.get("title", ""),
                    "node_type": node.get("node_type", "Concept"),
                    "summary": node.get("summary", ""),
                }
            for edge in delta.get("edges", []):
                edge_map[edge["edge_id"]] = {
                    "edge_id": edge["edge_id"],
                    "source_node_id": edge["source_node_id"],
                    "target_node_id": edge["target_node_id"],
                    "relation_type": edge.get("relation_type", "related_to"),
                }
        return FocusGraphResponse(
            graph_id=graph_id,
            center_node_id="",
            nodes=[GraphNode(**node) for node in node_map.values()],
            edges=[GraphEdge(**edge) for edge in edge_map.values()],
        )

    def focus_view(self, graph_id: str, node_id: str) -> FocusGraphResponse:
        graph_view = self.graph_view(graph_id)
        related_edges = [
            edge for edge in graph_view.edges
            if edge.source_node_id == node_id or edge.target_node_id == node_id
        ]
        related_node_ids = {node_id}
        for edge in related_edges:
            related_node_ids.add(edge.source_node_id)
            related_node_ids.add(edge.target_node_id)
        related_nodes = [node for node in graph_view.nodes if node.node_id in related_node_ids]
        return FocusGraphResponse(
            graph_id=graph_id,
            center_node_id=node_id,
            nodes=related_nodes,
            edges=related_edges,
        )

    def summarize_node(self, graph_id: str, node_id: str) -> GraphNode:
        graph_rows = self._load_json(self.graph_store_file)
        dynamic_rows = self._load_json(self.dynamic_chunks_file)
        chunk_by_id = {row.get('chunk_id'): row for row in dynamic_rows if row.get('graph_id') == graph_id}

        target_node = None
        related_edge_texts: list[str] = []
        evidence_snippets: list[str] = []
        for row in graph_rows:
            if row.get('graph_id') != graph_id:
                continue
            delta = row.get('delta', {})
            nodes = {node.get('node_id'): node for node in delta.get('nodes', [])}
            if node_id in nodes:
                target_node = nodes[node_id]
            for edge in delta.get('edges', []):
                if edge.get('source_node_id') == node_id or edge.get('target_node_id') == node_id:
                    source_title = nodes.get(edge.get('source_node_id'), {}).get('title', edge.get('source_node_id', ''))
                    target_title = nodes.get(edge.get('target_node_id'), {}).get('title', edge.get('target_node_id', ''))
                    related_edge_texts.append(f"{source_title} {edge.get('relation_type', 'related_to')} {target_title}")
            if node_id in nodes:
                for item in delta.get('evidence', [])[:3]:
                    chunk_id = item.get('chunk_id')
                    if chunk_id and chunk_id in chunk_by_id:
                        snippet = chunk_by_id[chunk_id].get('content', '')[:220]
                        if snippet:
                            evidence_snippets.append(snippet)
        if target_node is None:
            raise ValueError(f'Node not found: {node_id}')

        if target_node.get('summary'):
            return GraphNode(
                node_id=target_node['node_id'],
                title=target_node.get('title', ''),
                node_type=target_node.get('node_type', 'Concept'),
                summary=target_node.get('summary', ''),
            )

        prompt = (
            'You are writing a concise study-note summary for a knowledge graph node. '
            'Summarize what this concept is and why it matters in at most 60 Chinese characters. '
            'Be factual and avoid markdown.\n\n'
            f"Node: {target_node.get('title', '')}\n"
            f"Type: {target_node.get('node_type', 'Concept')}\n"
            f"Related facts: {related_edge_texts[:5]}\n"
            f"Evidence: {evidence_snippets[:3]}"
        )
        summary = DeepSeekClient().chat(prompt).strip()
        target_node['summary'] = summary[:120]
        self._save_json(self.graph_store_file, graph_rows)
        return GraphNode(
            node_id=target_node['node_id'],
            title=target_node.get('title', ''),
            node_type=target_node.get('node_type', 'Concept'),
            summary=target_node.get('summary', ''),
        )

    def review_candidates(self, graph_id: str, ids: list[str], action: str) -> ReviewResult:
        if action not in {"approve", "reject"}:
            raise ValueError("action must be approve or reject")

        rows = self._load_json(self.candidates_file)
        target_status = "reviewed" if action == "approve" else "rejected"
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            if row["graph_id"] == graph_id and row["candidate_delta_id"] in ids and row["status"] == "draft":
                row["status"] = target_status
                row["updated_at"] = now
        self._save_json(self.candidates_file, rows)
        return ReviewResult(graph_id=graph_id, action=action, candidate_ids=ids)

    def publish_candidates(self, graph_id: str, ids: list[str]) -> PublishResult:
        rows = self._load_json(self.candidates_file)
        graph_rows = self._load_json(self.graph_store_file)
        now = datetime.now(timezone.utc).isoformat()

        published: list[str] = []
        skipped: list[PublishSkippedItem] = []
        row_by_id = {row["candidate_delta_id"]: row for row in rows}

        for candidate_id in ids:
            row = row_by_id.get(candidate_id)
            if row is None:
                skipped.append(PublishSkippedItem(candidate_delta_id=candidate_id, reason="not_found"))
                continue
            if row["graph_id"] != graph_id:
                skipped.append(PublishSkippedItem(candidate_delta_id=candidate_id, reason="graph_mismatch"))
                continue
            if row["status"] != "reviewed":
                skipped.append(PublishSkippedItem(candidate_delta_id=candidate_id, reason="status_not_reviewed"))
                continue

            row["status"] = "published"
            row["updated_at"] = now
            graph_rows.append(
                {
                    "graph_id": graph_id,
                    "candidate_delta_id": row["candidate_delta_id"],
                    "delta": row["delta"],
                    "published_at": now,
                }
            )
            published.append(row["candidate_delta_id"])

        self._save_json(self.candidates_file, rows)
        self._save_json(self.graph_store_file, graph_rows)

        if published:
            self._materialize_published_facts(graph_id=graph_id, candidate_ids=published)
            self._sync_published_to_retrieval(graph_id=graph_id, candidate_ids=published)
            self._sync_published_to_neo4j(graph_id=graph_id, candidate_ids=published)
            LocalEmbeddingRetrievalService().precompute_embeddings(graph_id=graph_id)

        return PublishResult(graph_id=graph_id, published_ids=published, skipped=skipped)

    def list_candidates(
        self,
        graph_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CandidateDeltaRecord]:
        rows = self._load_json(self.candidates_file)
        records = [CandidateDeltaRecord(**row) for row in rows if row["graph_id"] == graph_id]
        if status is not None:
            records = [record for record in records if record.status == status]
        return records[offset: offset + limit]

    def clear_graph(self, graph_id: str) -> None:
        candidate_rows = [row for row in self._load_json(self.candidates_file) if row.get('graph_id') != graph_id]
        graph_rows = [row for row in self._load_json(self.graph_store_file) if row.get('graph_id') != graph_id]
        dynamic_rows = [row for row in self._load_json(self.dynamic_chunks_file) if row.get('graph_id') != graph_id]
        fact_rows = [row for row in self._load_json(self.facts_file) if row.get('graph_id') != graph_id]
        self._save_json(self.candidates_file, candidate_rows)
        self._save_json(self.graph_store_file, graph_rows)
        self._save_json(self.dynamic_chunks_file, dynamic_rows)
        self._save_json(self.facts_file, fact_rows)

    def _materialize_published_facts(self, graph_id: str, candidate_ids: list[str]) -> None:
        graph_rows = self._load_json(self.graph_store_file)
        fact_rows = self._load_json(self.facts_file)
        existing_fact_ids = {row.get("fact_id") for row in fact_rows}

        for row in graph_rows:
            if row.get("graph_id") != graph_id:
                continue
            if row.get("candidate_delta_id") not in candidate_ids:
                continue

            delta = row.get("delta", {})
            node_title_by_id = {node.get("node_id"): node.get("title", "") for node in delta.get("nodes", [])}
            chunk_ids = [item.get("chunk_id") for item in delta.get("evidence", []) if item.get("chunk_id")]

            for edge in delta.get("edges", []):
                source_node_id = edge.get("source_node_id")
                target_node_id = edge.get("target_node_id")
                relation_type = edge.get("relation_type", "related_to")
                fact_id = f"fact_{row['candidate_delta_id']}_{edge.get('edge_id')}"
                if fact_id in existing_fact_ids:
                    continue

                source_title = node_title_by_id.get(source_node_id, source_node_id or "")
                target_title = node_title_by_id.get(target_node_id, target_node_id or "")
                fact_rows.append(
                    FactRecord(
                        fact_id=fact_id,
                        graph_id=graph_id,
                        candidate_delta_id=row["candidate_delta_id"],
                        source_node_id=source_node_id or "",
                        source_title=source_title,
                        relation_type=relation_type,
                        target_node_id=target_node_id or "",
                        target_title=target_title,
                        fact_text=f"{source_title} {relation_type} {target_title}".strip(),
                        chunk_ids=chunk_ids,
                    ).model_dump()
                )
                existing_fact_ids.add(fact_id)

        self._save_json(self.facts_file, fact_rows)

    def _sync_published_to_neo4j(self, graph_id: str, candidate_ids: list[str]) -> None:
        store = self._get_neo4j_store()
        if store is None:
            return
        graph_rows = self._load_json(self.graph_store_file)
        for row in graph_rows:
            if row.get("graph_id") != graph_id:
                continue
            if row.get("candidate_delta_id") not in candidate_ids:
                continue
            delta = row.get("delta", {})
            evidence_chunk_ids = [item.get("chunk_id") for item in delta.get("evidence", []) if item.get("chunk_id")]
            store.sync_graph_delta(
                graph_id=graph_id,
                candidate_delta_id=row.get("candidate_delta_id", ""),
                delta=delta,
                evidence_chunk_ids=evidence_chunk_ids,
            )

    def _sync_published_to_retrieval(self, graph_id: str, candidate_ids: list[str]) -> None:
        graph_rows = self._load_json(self.graph_store_file)
        dynamic_chunks = self._load_json(self.dynamic_chunks_file)
        existing_ids = {row.get("chunk_id") for row in dynamic_chunks}

        for row in graph_rows:
            if row.get("graph_id") != graph_id:
                continue
            if row.get("candidate_delta_id") not in candidate_ids:
                continue

            delta = row.get("delta", {})
            for node in delta.get("nodes", []):
                chunk_id = f"published_{row['candidate_delta_id']}_{node.get('node_id')}"
                if chunk_id in existing_ids:
                    continue
                content = f"{node.get('node_type', 'Node')}: {node.get('title', '')}"
                dynamic_chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "document_id": f"graph_{graph_id}",
                        "graph_id": graph_id,
                        "content": content,
                    }
                )
                existing_ids.add(chunk_id)

        self._save_json(self.dynamic_chunks_file, dynamic_chunks)

    @staticmethod
    def _load_json(path: Path) -> list[dict]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _save_json(path: Path, rows: list[dict]) -> None:
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
