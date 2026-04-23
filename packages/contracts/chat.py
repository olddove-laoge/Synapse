from pydantic import BaseModel


class Citation(BaseModel):
    chunk_id: str
    score: float


class ChatRequest(BaseModel):
    workspace_id: str
    graph_id: str
    user_id: str
    message: str
    use_web_search: bool = False


class NodeChatRequest(BaseModel):
    workspace_id: str
    graph_id: str
    user_id: str
    node_id: str
    message: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    candidate_delta_id: str
