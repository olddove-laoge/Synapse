from fastapi import APIRouter

from packages.contracts.graph import NodeNoteCreate, NodeNotePatch, NodeNoteResponse
from packages.graph.notes_service import LocalNodeNoteService


router = APIRouter()
_note_service = LocalNodeNoteService()


@router.get("/nodes/{node_id}/notes", response_model=list[NodeNoteResponse])
def get_notes(node_id: str) -> list[NodeNoteResponse]:
    return _note_service.list_notes(node_id)


@router.post("/nodes/{node_id}/notes", response_model=NodeNoteResponse)
def create_note(node_id: str, req: NodeNoteCreate) -> NodeNoteResponse:
    return _note_service.create_note(node_id=node_id, content=req.content)


@router.patch("/notes/{note_id}", response_model=NodeNoteResponse)
def patch_note(note_id: str, req: NodeNotePatch) -> NodeNoteResponse:
    return _note_service.update_note(note_id=note_id, node_id=req.node_id, content=req.content)
