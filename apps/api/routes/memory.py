from fastapi import APIRouter

from packages.contracts.memory import MemoryRecord, MemoryRebuildResponse


router = APIRouter()


@router.get("/users/{user_id}/memory", response_model=list[MemoryRecord])
def user_memory(user_id: str) -> list[MemoryRecord]:
    return []


@router.post("/users/{user_id}/memory/rebuild", response_model=MemoryRebuildResponse)
def rebuild_memory(user_id: str) -> MemoryRebuildResponse:
    return MemoryRebuildResponse(user_id=user_id, job_id=f"job_memory_{user_id}", status="queued")
