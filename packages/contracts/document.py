from typing import Literal

from pydantic import BaseModel


class DocumentRecord(BaseModel):
    document_id: str
    workspace_id: str
    graph_id: str
    filename: str
    file_path: str
    content_type: str | None = None


class ParsedChunk(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    section_path: list[str] = []
    page_start: int | None = None
    page_end: int | None = None
    source_type: Literal["pdf", "docx", "web", "chat", "md", "txt"]
    metadata: dict = {}


class DocumentUploadResponse(BaseModel):
    document_id: str
    status: Literal["uploaded"]


class ParseDocumentResponse(BaseModel):
    document_id: str
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    chunk_count: int = 0
