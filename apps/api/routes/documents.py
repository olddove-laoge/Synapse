from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from packages.common.config import app_config
from packages.contracts.document import DocumentUploadResponse, ParseDocumentResponse
from packages.extraction.hipporag_openie_adapter import HippoRAGOpenIEAdapter
from packages.graph.service import LocalGraphService
from packages.ingestion.llamaparse_adapter import LlamaParseAdapter
from packages.ingestion.service import LocalDocumentStore, IngestionService


router = APIRouter()
_store = LocalDocumentStore()
_ingestion_service: IngestionService | None = None
_graph_service = LocalGraphService()
_openie_adapter = HippoRAGOpenIEAdapter()


def get_ingestion_service() -> IngestionService:
    global _ingestion_service
    if _ingestion_service is None:
        llamaparse_adapter = None
        if app_config.llamaparse_api_key:
            llamaparse_adapter = LlamaParseAdapter()
        _ingestion_service = IngestionService(store=_store, llamaparse_adapter=llamaparse_adapter)
    return _ingestion_service


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    workspace_id: str = Form(...),
    graph_id: str = Form(...),
) -> DocumentUploadResponse:
    content = await file.read()
    record = _store.save_upload(
        workspace_id=workspace_id,
        graph_id=graph_id,
        filename=file.filename,
        content=content,
        content_type=file.content_type,
    )
    return DocumentUploadResponse(document_id=record.document_id, status="uploaded")


@router.post("/documents/{document_id}/parse", response_model=ParseDocumentResponse)
def parse_document(document_id: str) -> ParseDocumentResponse:
    try:
        record = _store.get_document(document_id)
        if record is None:
            raise ValueError(f"Document not found: {document_id}")

        chunks = get_ingestion_service().parse_document(document_id=document_id)

        delta = _openie_adapter.extract_from_chunks(chunks)
        if delta.nodes or delta.edges:
            _graph_service.apply_delta(graph_id=record.graph_id, delta=delta, source="doc_parse")

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Parse failed: {exc}") from exc

    return ParseDocumentResponse(
        document_id=document_id,
        job_id=f"job_parse_{document_id}",
        status="completed",
        chunk_count=len(chunks),
    )
