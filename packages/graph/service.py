import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Literal
from uuid import uuid4

from pydantic import BaseModel

from packages.common.config import app_config
from packages.contracts.graph import FactRecord, FocusGraphResponse, GraphDelta, PublishCandidatesResponse, PublishSkippedItem
from packages.graph.neo4j_store import Neo4jGraphStore
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

    def focus_view(self, graph_id: str, node_id: str) -> FocusGraphResponse:
        return FocusGraphResponse(graph_id=graph_id, center_node_id=node_id, nodes=[], edges=[])

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
