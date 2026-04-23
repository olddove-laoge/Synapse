from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from packages.contracts.graph import FocusGraphResponse, GraphNodeCreate, GraphEdgeCreate, PublishCandidatesResponse
from packages.graph.service import LocalGraphService


router = APIRouter()
_graph_service = LocalGraphService()


class CandidateReviewRequest(BaseModel):
    candidate_ids: list[str]
    action: Literal["approve", "reject"]


class CandidatePublishRequest(BaseModel):
    candidate_ids: list[str]


@router.get("/graphs/{graph_id}/focus", response_model=FocusGraphResponse)
def graph_focus(graph_id: str, node_id: str) -> FocusGraphResponse:
    return FocusGraphResponse(graph_id=graph_id, center_node_id=node_id, nodes=[], edges=[])


@router.post("/graphs/{graph_id}/nodes")
def create_node(graph_id: str, req: GraphNodeCreate) -> dict[str, str]:
    return {"graph_id": graph_id, "node_id": req.node_id}


@router.post("/graphs/{graph_id}/edges")
def create_edge(graph_id: str, req: GraphEdgeCreate) -> dict[str, str]:
    return {"graph_id": graph_id, "edge_id": req.edge_id}


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
