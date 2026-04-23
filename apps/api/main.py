from fastapi import FastAPI

from apps.api.routes import chat, documents, graphs, notes, memory


app = FastAPI(title="Synapse API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(graphs.router, prefix="/api/v1", tags=["graphs"])
app.include_router(notes.router, prefix="/api/v1", tags=["notes"])
app.include_router(memory.router, prefix="/api/v1", tags=["memory"])
