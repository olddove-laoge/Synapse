import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

import apps.api.main as api_main
from apps.api.routes import chat, documents, graphs
from packages.contracts.graph import CandidateEdge, CandidateNode, EvidenceItem, GraphDelta
from packages.graph.service import LocalGraphService
from packages.ingestion.service import IngestionService, LocalDocumentStore
from packages.retrieval.service import LocalEmbeddingRetrievalService


class FakeEmbedClient:
    def embed(self, text: str):
        return fake_embed(self, text)


class FakeOpenIEAdapter:
    def extract_from_chunks(self, chunks):
        if not chunks:
            return GraphDelta(nodes=[], edges=[], evidence=[])
        chunk = chunks[0]
        return GraphDelta(
            nodes=[
                CandidateNode(node_id="node_doc_subject", title="Transformer", node_type="Concept", status="draft"),
                CandidateNode(node_id="node_doc_object", title="Attention", node_type="Concept", status="draft"),
            ],
            edges=[
                CandidateEdge(
                    edge_id="edge_doc_rel",
                    source_node_id="node_doc_subject",
                    target_node_id="node_doc_object",
                    relation_type="uses",
                    status="draft",
                )
            ],
            evidence=[EvidenceItem(evidence_id=f"ev_{chunk.chunk_id}", chunk_id=chunk.chunk_id, score=0.9)],
        )


def fake_embed(self, text: str):
    base = float((len(text) % 7) + 1)
    return [base, base / 2.0, 1.0]


def fake_chat(self, message: str, system_prompt: str | None = None):
    return "Transformer uses attention and supports contextual encoding."


class PipelineIntegrationTest(unittest.TestCase):
    def test_parse_publish_chat_pipeline(self):
        old_store = documents._store
        old_ingestion_service = documents._ingestion_service
        old_graph_service_documents = documents._graph_service
        old_openie = documents._openie_adapter
        old_graph_service_graphs = graphs._graph_service
        old_graph_service_chat = chat._graph_service
        old_retrieval_service = chat._retrieval_service

        with TemporaryDirectory() as tmp_dir:
            data_root = Path(tmp_dir)
            store = LocalDocumentStore(data_root=str(data_root))
            graph_service = LocalGraphService(data_root=str(data_root))
            retrieval_service = LocalEmbeddingRetrievalService(
                chunk_file_path=str(data_root / "dynamic_chunks.json"),
                embedding_cache_file_path=str(data_root / "chunk_embeddings.json"),
                documents_file_path=str(data_root / "documents.json"),
                facts_file_path=str(data_root / "facts.json"),
                fact_embedding_cache_file_path=str(data_root / "fact_embeddings.json"),
                embed_client=FakeEmbedClient(),
            )
            ingestion_service = IngestionService(store=store, retrieval_service=retrieval_service)

            documents._store = store
            documents._ingestion_service = ingestion_service
            documents._graph_service = graph_service
            documents._openie_adapter = FakeOpenIEAdapter()
            graphs._graph_service = graph_service
            chat._graph_service = graph_service
            chat._retrieval_service = retrieval_service

            with patch("packages.embedding.aliyun_client.AliyunEmbeddingClient.embed", new=fake_embed), patch(
                "packages.llm.deepseek_client.DeepSeekClient.chat", new=fake_chat
            ):
                client = TestClient(api_main.app)

                upload_resp = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("demo.txt", b"Transformer architecture uses attention mechanisms.", "text/plain")},
                    data={"workspace_id": "ws_demo", "graph_id": "g_demo"},
                )
                self.assertEqual(upload_resp.status_code, 200)
                document_id = upload_resp.json()["document_id"]

                parse_resp = client.post(f"/api/v1/documents/{document_id}/parse")
                self.assertEqual(parse_resp.status_code, 200)
                self.assertEqual(parse_resp.json()["status"], "completed")

                candidates_resp = client.get("/api/v1/graphs/g_demo/candidates", params={"status": "draft"})
                self.assertEqual(candidates_resp.status_code, 200)
                rows = candidates_resp.json()
                self.assertTrue(len(rows) > 0)
                doc_parse_row = next(row for row in rows if row["source"] == "doc_parse")
                candidate_id = doc_parse_row["candidate_delta_id"]
                self.assertTrue(len(doc_parse_row["delta"]["nodes"]) > 0)
                self.assertTrue(len(doc_parse_row["delta"]["edges"]) > 0)

                review_resp = client.post(
                    "/api/v1/graphs/g_demo/candidates/review",
                    json={"candidate_ids": [candidate_id], "action": "approve"},
                )
                self.assertEqual(review_resp.status_code, 200)

                publish_resp = client.post(
                    "/api/v1/graphs/g_demo/candidates/publish",
                    json={"candidate_ids": [candidate_id]},
                )
                self.assertEqual(publish_resp.status_code, 200)
                publish_body = publish_resp.json()
                self.assertIn(candidate_id, publish_body["published_ids"])
                self.assertEqual(publish_body["skipped"], [])
                facts_path = data_root / "facts.json"
                self.assertTrue(facts_path.exists())
                self.assertTrue(len(facts_path.read_text(encoding="utf-8")) > 2)

                second_publish_resp = client.post(
                    "/api/v1/graphs/g_demo/candidates/publish",
                    json={"candidate_ids": [candidate_id]},
                )
                self.assertEqual(second_publish_resp.status_code, 200)
                second_publish_body = second_publish_resp.json()
                self.assertEqual(second_publish_body["published_ids"], [])
                self.assertEqual(second_publish_body["skipped"][0]["reason"], "status_not_reviewed")

                chat_resp = client.post(
                    "/api/v1/chat",
                    json={
                        "workspace_id": "ws_demo",
                        "graph_id": "g_demo",
                        "user_id": "u_demo",
                        "message": "What does transformer use?",
                        "use_web_search": False,
                    },
                )
                self.assertEqual(chat_resp.status_code, 200)
                citations = chat_resp.json()["citations"]
                self.assertTrue(any(item["chunk_id"].startswith(f"{document_id}_chunk_") for item in citations))

        documents._store = old_store
        documents._ingestion_service = old_ingestion_service
        documents._graph_service = old_graph_service_documents
        documents._openie_adapter = old_openie
        graphs._graph_service = old_graph_service_graphs
        chat._graph_service = old_graph_service_chat
        chat._retrieval_service = old_retrieval_service


if __name__ == "__main__":
    unittest.main()
