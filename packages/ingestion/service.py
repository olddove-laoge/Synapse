import json
import re
from pathlib import Path
from uuid import uuid4

from packages.contracts.document import DocumentRecord, ParsedChunk
from packages.ingestion.llamaparse_adapter import LlamaParseAdapter
from packages.retrieval.service import LocalEmbeddingRetrievalService


class LocalDocumentStore:
    def __init__(self, data_root: str | None = None) -> None:
        if data_root is None:
            data_root = str(Path(__file__).resolve().parents[2] / "data")
        self.data_root = Path(data_root)
        self.upload_root = self.data_root / "uploads"
        self.upload_root.mkdir(parents=True, exist_ok=True)
        self.documents_file = self.data_root / "documents.json"
        self.dynamic_chunks_file = self.data_root / "dynamic_chunks.json"
        if not self.documents_file.exists():
            self.documents_file.write_text("[]", encoding="utf-8")
        if not self.dynamic_chunks_file.exists():
            self.dynamic_chunks_file.write_text("[]", encoding="utf-8")

    def save_upload(
        self,
        workspace_id: str,
        graph_id: str,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> DocumentRecord:
        document_id = f"doc_{uuid4().hex}"
        safe_name = f"{document_id}_{filename}"
        file_path = self.upload_root / safe_name
        file_path.write_bytes(content)

        record = DocumentRecord(
            document_id=document_id,
            workspace_id=workspace_id,
            graph_id=graph_id,
            filename=filename,
            file_path=str(file_path),
            content_type=content_type,
        )

        docs = self._load_json(self.documents_file)
        docs.append(record.model_dump())
        self._save_json(self.documents_file, docs)
        return record

    def register_existing_file(
        self,
        workspace_id: str,
        graph_id: str,
        filename: str,
        file_path: str,
        content_type: str | None,
    ) -> DocumentRecord:
        record = DocumentRecord(
            document_id=f"doc_{uuid4().hex}",
            workspace_id=workspace_id,
            graph_id=graph_id,
            filename=filename,
            file_path=file_path,
            content_type=content_type,
        )

        docs = self._load_json(self.documents_file)
        docs.append(record.model_dump())
        self._save_json(self.documents_file, docs)
        return record

    def get_document(self, document_id: str) -> DocumentRecord | None:
        docs = self._load_json(self.documents_file)
        for item in docs:
            if item["document_id"] == document_id:
                return DocumentRecord(**item)
        return None

    def save_chunks(self, chunks: list[ParsedChunk]) -> None:
        existing = self._load_json(self.dynamic_chunks_file)
        docs = self._load_json(self.documents_file)
        graph_id_by_document_id = {item["document_id"]: item.get("graph_id") for item in docs}
        existing_by_id = {item["chunk_id"]: item for item in existing}
        for chunk in chunks:
            existing_by_id[chunk.chunk_id] = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "graph_id": graph_id_by_document_id.get(chunk.document_id),
                "content": chunk.content,
                "section_path": chunk.section_path,
                "summary": chunk.summary,
            }
        self._save_json(self.dynamic_chunks_file, list(existing_by_id.values()))

    @staticmethod
    def _load_json(path: Path) -> list[dict]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _save_json(path: Path, rows: list[dict]) -> None:
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


class IngestionService:
    def __init__(
        self,
        store: LocalDocumentStore | None = None,
        chunk_size: int = 600,
        retrieval_service: LocalEmbeddingRetrievalService | None = None,
        llamaparse_adapter: LlamaParseAdapter | None = None,
    ) -> None:
        self.store = store or LocalDocumentStore()
        self.chunk_size = chunk_size
        self.retrieval_service = retrieval_service or LocalEmbeddingRetrievalService()
        self.llamaparse_adapter = llamaparse_adapter

    def parse_document(self, document_id: str, source_uri: str | None = None) -> list[ParsedChunk]:
        record = self.store.get_document(document_id)
        if record is None:
            raise ValueError(f"Document not found: {document_id}")

        source_type = self._infer_source_type(record.filename)
        text = self._load_document_text(record.file_path, record.filename)
        chunks = self._split_into_chunks(document_id=document_id, text=text, source_type=source_type)
        self.store.save_chunks(chunks)
        self.retrieval_service.precompute_embeddings(
            graph_id=record.graph_id,
            chunk_ids=[chunk.chunk_id for chunk in chunks],
        )
        return chunks

    def _load_document_text(self, file_path: str, filename: str) -> str:
        path = Path(file_path)
        if self.llamaparse_adapter and self.llamaparse_adapter.should_use_llamaparse(filename):
            try:
                markdown = self.llamaparse_adapter.parse_to_markdown(str(path))
                if markdown.strip():
                    return markdown
            except Exception:
                pass
        return path.read_text(encoding="utf-8", errors="ignore")

    def _split_into_chunks(self, document_id: str, text: str, source_type: str) -> list[ParsedChunk]:
        lines = [line.rstrip() for line in text.splitlines()]
        if not any(line.strip() for line in lines):
            return []

        chunks: list[ParsedChunk] = []
        heading_stack: list[tuple[int, str]] = []
        buffer: list[str] = []
        start_offset = 0
        index = 0
        offset = 0

        def current_section_path() -> list[str]:
            return [title for _, title in heading_stack]

        def summarize(content: str, section_path: list[str]) -> str:
            base = section_path[-1] if section_path else content
            summary = " ".join(base.split())[:30].strip()
            return summary or "未命名片段"

        def emit_chunk() -> None:
            nonlocal buffer, start_offset, index
            content = "\n".join(line for line in buffer if line.strip()).strip()
            if not content:
                buffer = []
                return
            section_path = current_section_path()
            chunks.append(
                ParsedChunk(
                    chunk_id=f"{document_id}_chunk_{index}",
                    document_id=document_id,
                    content=content,
                    section_path=section_path,
                    summary=summarize(content, section_path),
                    source_type=source_type,
                    metadata={"offset": start_offset},
                )
            )
            index += 1
            buffer = []

        for line in lines:
            stripped = line.strip()
            heading_level = len(stripped) - len(stripped.lstrip('#')) if stripped.startswith('#') else 0
            if heading_level > 0 and stripped.lstrip('#').strip():
                emit_chunk()
                heading_title = stripped[heading_level:].strip()
                while heading_stack and heading_stack[-1][0] >= heading_level:
                    heading_stack.pop()
                heading_stack.append((heading_level, heading_title))
                start_offset = offset
            else:
                if not buffer:
                    start_offset = offset
                buffer.append(line)
            offset += len(line) + 1

        emit_chunk()

        oversized: list[ParsedChunk] = []
        for chunk in chunks:
            words = chunk.content.split()
            if len(words) <= 280:
                oversized.append(chunk)
                continue
            sentences = [part.strip() for part in re.split(r'(?<=[.!?。！？])\s+', chunk.content) if part.strip()]
            piece: list[str] = []
            sub_index = 0
            for sentence in sentences:
                candidate = (" ".join(piece + [sentence])).strip()
                if piece and len(candidate.split()) > 280:
                    oversized.append(
                        ParsedChunk(
                            chunk_id=f"{chunk.chunk_id}_part_{sub_index}",
                            document_id=document_id,
                            content=" ".join(piece).strip(),
                            section_path=chunk.section_path,
                            summary=chunk.summary,
                            source_type=source_type,
                            metadata=chunk.metadata,
                        )
                    )
                    sub_index += 1
                    piece = [sentence]
                else:
                    piece.append(sentence)
            if piece:
                oversized.append(
                    ParsedChunk(
                        chunk_id=f"{chunk.chunk_id}_part_{sub_index}" if sub_index else chunk.chunk_id,
                        document_id=document_id,
                        content=" ".join(piece).strip(),
                        section_path=chunk.section_path,
                        summary=chunk.summary,
                        source_type=source_type,
                        metadata=chunk.metadata,
                    )
                )
        return oversized

    @staticmethod
    def _infer_source_type(filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix == ".md":
            return "md"
        if suffix == ".txt":
            return "txt"
        if suffix == ".pdf":
            return "pdf"
        if suffix == ".docx":
            return "docx"
        return "web"
