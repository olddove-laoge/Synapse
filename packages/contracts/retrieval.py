from pydantic import BaseModel

from packages.contracts.graph import EvidenceItem


class RetrievalRequest(BaseModel):
    graph_id: str
    query: str
    top_k: int = 10


class RetrievedPassage(BaseModel):
    chunk_id: str
    content: str
    score: float


class RetrievalResult(BaseModel):
    passages: list[str]
    evidence: list[EvidenceItem]
    retrieved_passages: list[RetrievedPassage] = []
