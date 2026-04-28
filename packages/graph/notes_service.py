import json
from pathlib import Path
from uuid import uuid4

from packages.contracts.graph import NodeNoteResponse


class LocalNodeNoteService:
    def __init__(self, data_root: str | None = None) -> None:
        if data_root is None:
            data_root = str(Path(__file__).resolve().parents[2] / 'data')
        self.data_root = Path(data_root)
        self.notes_file = self.data_root / 'node_notes.json'
        if not self.notes_file.exists():
            self.notes_file.write_text('[]', encoding='utf-8')

    def list_notes(self, node_id: str) -> list[NodeNoteResponse]:
        rows = self._load_json()
        return [NodeNoteResponse(**row) for row in rows if row.get('node_id') == node_id]

    def create_note(self, node_id: str, content: str) -> NodeNoteResponse:
        rows = self._load_json()
        note = NodeNoteResponse(note_id=f'note_{uuid4().hex}', node_id=node_id, content=content)
        rows.append(note.model_dump())
        self._save_json(rows)
        return note

    def update_note(self, note_id: str, node_id: str, content: str) -> NodeNoteResponse:
        rows = self._load_json()
        for row in rows:
            if row.get('note_id') == note_id:
                row['node_id'] = node_id
                row['content'] = content
                self._save_json(rows)
                return NodeNoteResponse(**row)
        note = NodeNoteResponse(note_id=note_id, node_id=node_id, content=content)
        rows.append(note.model_dump())
        self._save_json(rows)
        return note

    def _load_json(self) -> list[dict]:
        return json.loads(self.notes_file.read_text(encoding='utf-8'))

    def _save_json(self, rows: list[dict]) -> None:
        self.notes_file.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
