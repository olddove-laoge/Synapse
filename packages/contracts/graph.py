from typing import Literal

from pydantic import BaseModel


CandidateStatus = Literal["draft", "reviewed", "published", "rejected", "merged"]


class GraphNode(BaseModel):
    node_id: str
    title: str
    node_type: str
    confidence: float | None = None


class GraphEdge(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str
    confidence: float | None = None


class GraphNodeCreate(BaseModel):
    node_id: str
    title: str
    node_type: str


class GraphEdgeCreate(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str


class FocusGraphResponse(BaseModel):
    graph_id: str
    center_node_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class NodeNoteCreate(BaseModel):
    content: str


class NodeNotePatch(BaseModel):
    node_id: str
    content: str


class NodeNoteResponse(BaseModel):
    note_id: str
    node_id: str
    content: str


class EvidenceItem(BaseModel):
    evidence_id: str
    chunk_id: str
    score: float


class CandidateNode(BaseModel):
    node_id: str
    title: str
    node_type: str
    status: CandidateStatus = "draft"


class CandidateEdge(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str
    status: CandidateStatus = "draft"


class GraphDelta(BaseModel):
    nodes: list[CandidateNode] = []
    edges: list[CandidateEdge] = []
    evidence: list[EvidenceItem] = []


class PublishSkippedItem(BaseModel):
    candidate_delta_id: str
    reason: Literal["not_found", "graph_mismatch", "status_not_reviewed"]


class PublishCandidatesResponse(BaseModel):
    graph_id: str
    published_ids: list[str]
    skipped: list[PublishSkippedItem] = []


class FactRecord(BaseModel):
    fact_id: str
    graph_id: str
    candidate_delta_id: str
    source_node_id: str
    source_title: str
    relation_type: str
    target_node_id: str
    target_title: str
    fact_text: str
    chunk_ids: list[str] = []
