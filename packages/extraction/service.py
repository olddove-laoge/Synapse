from typing import Protocol

from pydantic import BaseModel

from packages.contracts.document import ParsedChunk
from packages.contracts.graph import GraphDelta
from packages.extraction.hipporag_openie_adapter import HippoRAGOpenIEAdapter


class ChatTurn(BaseModel):
    role: str
    content: str


class ExtractionService(Protocol):
    def extract_from_chunks(self, chunks: list[ParsedChunk]) -> GraphDelta: ...

    def extract_from_chat(self, question: str, answer: str, citations: list[dict]) -> GraphDelta: ...


class LocalExtractionService:
    def __init__(self) -> None:
        self._openie_adapter = HippoRAGOpenIEAdapter()

    def extract_from_chunks(self, chunks: list[ParsedChunk]) -> GraphDelta:
        return self._openie_adapter.extract_from_chunks(chunks)

    def extract_from_chat(self, question: str, answer: str, citations: list[dict]) -> GraphDelta:
        q = question.strip()
        a = answer.strip()
        if not q or not a:
            return GraphDelta(nodes=[], edges=[], evidence=[])

        chat_text = f"Question: {q}\n\nAnswer: {a}"
        chat_chunk = ParsedChunk(
            chunk_id=f"chat_{abs(hash(chat_text)) % 10**12}",
            document_id="chat_session",
            content=chat_text,
            source_type="chat",
            metadata={"citations": citations},
        )

        return self._openie_adapter.extract_from_chunks([chat_chunk])
