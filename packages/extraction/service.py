from typing import Protocol

from pydantic import BaseModel

from packages.contracts.document import ParsedChunk
from packages.contracts.graph import GraphDelta, CandidateNode, CandidateEdge, EvidenceItem


class ChatTurn(BaseModel):
    role: str
    content: str


class ExtractionService(Protocol):
    def extract_from_chunks(self, chunks: list[ParsedChunk]) -> GraphDelta: ...

    def extract_from_chat(self, question: str, answer: str, citations: list[dict]) -> GraphDelta: ...


class LocalExtractionService:
    def extract_from_chunks(self, chunks: list[ParsedChunk]) -> GraphDelta:
        return GraphDelta()

    def extract_from_chat(self, question: str, answer: str, citations: list[dict]) -> GraphDelta:
        q = question.strip()
        a = answer.strip()
        if not q or not a:
            return GraphDelta(nodes=[], edges=[], evidence=[])

        if len(q) < 3 or len(a) < 20:
            return GraphDelta(nodes=[], edges=[], evidence=[])

        if "不知道" in a and len(citations) == 0:
            return GraphDelta(nodes=[], edges=[], evidence=[])

        q_node_id = f"node_q_{abs(hash(q)) % 10**10}"
        a_node_id = f"node_a_{abs(hash(a[:300])) % 10**10}"

        nodes = [
            CandidateNode(
                node_id=q_node_id,
                title=q[:80],
                node_type="Question",
                status="draft",
            ),
            CandidateNode(
                node_id=a_node_id,
                title=a[:120],
                node_type="Insight",
                status="draft",
            ),
        ]

        edges = [
            CandidateEdge(
                edge_id=f"edge_{q_node_id}_{a_node_id}",
                source_node_id=q_node_id,
                target_node_id=a_node_id,
                relation_type="answered_by",
                status="draft",
            )
        ]

        evidence = []
        for item in citations:
            chunk_id = item.get("chunk_id")
            score = float(item.get("score", 0.0))
            if (not chunk_id) or score < 0.25:
                continue
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{chunk_id}",
                    chunk_id=chunk_id,
                    score=score,
                )
            )

        if not evidence:
            return GraphDelta(nodes=[], edges=[], evidence=[])

        return GraphDelta(nodes=nodes, edges=edges, evidence=evidence)
