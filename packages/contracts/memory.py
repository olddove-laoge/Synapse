from typing import Literal

from pydantic import BaseModel


class MemoryRecord(BaseModel):
    memory_id: str
    user_id: str
    content: str
    importance: float = 0.5


class MemoryRecallRequest(BaseModel):
    user_id: str
    query: str
    top_k: int = 5


class MemoryWriteRequest(BaseModel):
    user_id: str
    content: str
    source: Literal["chat", "note", "system"]


class MemoryRebuildResponse(BaseModel):
    user_id: str
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
