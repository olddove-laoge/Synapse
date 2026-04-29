from fastapi import APIRouter

from packages.contracts.document import ManualChunkCreate, ManualChunkResponse
from packages.graph.manual_chunk_service import LocalManualChunkService


router = APIRouter()
_chunk_service = LocalManualChunkService()


@router.get('/graphs/{graph_id}/manual-chunks', response_model=list[ManualChunkResponse])
def list_manual_chunks(graph_id: str) -> list[ManualChunkResponse]:
    return _chunk_service.list_chunks(graph_id)


@router.post('/graphs/{graph_id}/manual-chunks', response_model=ManualChunkResponse)
def create_manual_chunk(graph_id: str, req: ManualChunkCreate) -> ManualChunkResponse:
    return _chunk_service.create_chunk(
        graph_id=graph_id,
        title=req.title,
        content=req.content,
        linked_node_ids=req.linked_node_ids,
    )
