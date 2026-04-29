from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from packages.contracts.graph import FocusGraphResponse, GraphNode, GraphNodeCreate, GraphEdgeCreate, PublishCandidatesResponse
from packages.graph.service import LocalGraphService


router = APIRouter()
_graph_service = LocalGraphService()


class CandidateReviewRequest(BaseModel):
    candidate_ids: list[str]
    action: Literal["approve", "reject"]


class CandidatePublishRequest(BaseModel):
    candidate_ids: list[str]


@router.delete("/graphs/{graph_id}")
def clear_graph(graph_id: str) -> dict[str, str]:
    _graph_service.clear_graph(graph_id=graph_id)
    return {"graph_id": graph_id, "status": "cleared"}


@router.get("/graphs/{graph_id}", response_model=FocusGraphResponse)
def graph_view(graph_id: str) -> FocusGraphResponse:
    return _graph_service.graph_view(graph_id=graph_id)


@router.get("/graphs/{graph_id}/focus", response_model=FocusGraphResponse)
def graph_focus(graph_id: str, node_id: str) -> FocusGraphResponse:
    return _graph_service.focus_view(graph_id=graph_id, node_id=node_id)


@router.post("/graphs/{graph_id}/nodes/{node_id}/summarize", response_model=GraphNode)
def summarize_node(graph_id: str, node_id: str) -> GraphNode:
    return _graph_service.summarize_node(graph_id=graph_id, node_id=node_id)


@router.post('/graphs/{graph_id}/nodes')
def create_node(graph_id: str, req: GraphNodeCreate) -> dict:
    node_id = _graph_service.create_manual_node(graph_id, req.node_id, req.title, req.node_type, req.summary)
    return {'graph_id': graph_id, 'node_id': node_id}


@router.post('/graphs/{graph_id}/edges')
def create_edge(graph_id: str, req: GraphEdgeCreate) -> dict:
    edge_id = _graph_service.create_manual_edge(graph_id, req.edge_id, req.source_node_id, req.target_node_id, req.relation_type)
    return {'graph_id': graph_id, 'edge_id': edge_id}


@router.get("/graphs/{graph_id}/candidates")
def list_candidates(
    graph_id: str,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    rows = _graph_service.list_candidates(
        graph_id=graph_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [row.model_dump() for row in rows]


@router.post("/graphs/{graph_id}/candidates/review")
def review_candidates(graph_id: str, req: CandidateReviewRequest) -> dict:
    try:
        result = _graph_service.review_candidates(graph_id=graph_id, ids=req.candidate_ids, action=req.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump()


@router.post("/graphs/{graph_id}/candidates/publish", response_model=PublishCandidatesResponse)
def publish_candidates(graph_id: str, req: CandidatePublishRequest) -> PublishCandidatesResponse:
    result = _graph_service.publish_candidates(graph_id=graph_id, ids=req.candidate_ids)
    return result
