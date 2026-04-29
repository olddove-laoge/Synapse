import json
from pathlib import Path
from uuid import uuid4

from packages.contracts.document import ManualChunkResponse


class LocalManualChunkService:
    def __init__(self, data_root: str | None = None) -> None:
        if data_root is None:
            data_root = str(Path(__file__).resolve().parents[2] / 'data')
        self.data_root = Path(data_root)
        self.chunks_file = self.data_root / 'manual_chunks.json'
        if not self.chunks_file.exists():
            self.chunks_file.write_text('[]', encoding='utf-8')

    def list_chunks(self, graph_id: str) -> list[ManualChunkResponse]:
        rows = self._load_json()
        return [ManualChunkResponse(**row) for row in rows if row.get('graph_id') == graph_id]

    def create_chunk(self, graph_id: str, title: str, content: str, linked_node_ids: list[str]) -> ManualChunkResponse:
        rows = self._load_json()
        chunk = ManualChunkResponse(
            chunk_id=f'manual_chunk_{uuid4().hex}',
            graph_id=graph_id,
            title=title,
            content=content,
            linked_node_ids=linked_node_ids,
        )
        rows.append(chunk.model_dump())
        self._save_json(rows)
        return chunk

    def _load_json(self) -> list[dict]:
        return json.loads(self.chunks_file.read_text(encoding='utf-8'))

    def _save_json(self, rows: list[dict]) -> None:
        self.chunks_file.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
