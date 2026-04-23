from typing import Protocol

from packages.contracts.memory import MemoryRecallRequest, MemoryWriteRequest, MemoryRecord


class MemoryService(Protocol):
    def recall(self, req: MemoryRecallRequest) -> list[MemoryRecord]: ...

    def write(self, req: MemoryWriteRequest) -> None: ...


class StubMemoryService:
    def recall(self, req: MemoryRecallRequest) -> list[MemoryRecord]:
        return []

    def write(self, req: MemoryWriteRequest) -> None:
        return None
