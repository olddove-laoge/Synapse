from fastapi import APIRouter, HTTPException

from packages.contracts.chat import ChatRequest, ChatResponse, NodeChatRequest
from packages.contracts.retrieval import RetrievalRequest
from packages.extraction.service import LocalExtractionService
from packages.graph.service import LocalGraphService
from packages.llm.deepseek_client import DeepSeekClient
from packages.retrieval.service import LocalEmbeddingRetrievalService


router = APIRouter()
_retrieval_service: LocalEmbeddingRetrievalService | None = None
_extraction_service = LocalExtractionService()
_graph_service = LocalGraphService()


def get_retrieval_service() -> LocalEmbeddingRetrievalService:
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = LocalEmbeddingRetrievalService()
    return _retrieval_service


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        retrieval_service = get_retrieval_service()
        retrieval = retrieval_service.retrieve_for_query(
            RetrievalRequest(graph_id=req.graph_id, query=req.message, top_k=3)
        )
        context_block = "\n\n".join(
            [f"[{idx + 1}] {passage.content}" for idx, passage in enumerate(retrieval.retrieved_passages)]
        )

        prompt = (
            "You are Synapse assistant.\n"
            "Task:\n"
            "1) Answer primarily based on the Retrieved Context.\n"
            "2) If context is insufficient, provide a second short section labeled '模型补充' based on general model knowledge.\n"
            "3) If context is sufficient, do not add '模型补充'.\n"
            "4) Keep the answer concise and accurate.\n\n"
            f"Retrieved Context:\n{context_block}\n\n"
            f"User Question:\n{req.message}"
        )

        client = DeepSeekClient()
        answer = client.chat(prompt)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat pipeline failed: {exc}") from exc

    citations = [{"chunk_id": item.chunk_id, "score": item.score} for item in retrieval.retrieved_passages]
    delta = _extraction_service.extract_from_chat(question=req.message, answer=answer, citations=citations)
    candidate_delta_id = _graph_service.apply_delta(graph_id=req.graph_id, delta=delta, source="chat")

    return ChatResponse(
        answer=answer,
        citations=citations,
        candidate_delta_id=candidate_delta_id,
    )


@router.post("/chat/node", response_model=ChatResponse)
def chat_node(req: NodeChatRequest) -> ChatResponse:
    try:
        retrieval_service = get_retrieval_service()
        retrieval = retrieval_service.retrieve_for_node(
            graph_id=req.graph_id,
            node_id=req.node_id,
            query=req.message,
        )
        context_block = "\n\n".join(
            [f"[{idx + 1}] {passage.content}" for idx, passage in enumerate(retrieval.retrieved_passages)]
        )

        client = DeepSeekClient()
        answer = client.chat(
            message=(
                "You are handling node-centric QA.\n"
                "First answer from retrieved context; if insufficient, append a short '模型补充'.\n\n"
                f"Node ID:\n{req.node_id}\n\n"
                f"Retrieved Context:\n{context_block}\n\n"
                f"User Question:\n{req.message}"
            ),
            system_prompt="Answer with node-centric explanation and keep uncertainty explicit.",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Node chat pipeline failed: {exc}") from exc

    citations = [{"chunk_id": item.chunk_id, "score": item.score} for item in retrieval.retrieved_passages]
    delta = _extraction_service.extract_from_chat(question=req.message, answer=answer, citations=citations)
    candidate_delta_id = _graph_service.apply_delta(graph_id=req.graph_id, delta=delta, source="node_chat")

    return ChatResponse(
        answer=answer,
        citations=citations,
        candidate_delta_id=candidate_delta_id,
    )
