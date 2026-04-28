from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from apps.api.routes import chat, documents, graphs, notes, memory


app = FastAPI(title="Synapse API", version="0.1.0")
static_dir = Path(__file__).resolve().parents[2] / "web"
if static_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="ui")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(graphs.router, prefix="/api/v1", tags=["graphs"])
app.include_router(notes.router, prefix="/api/v1", tags=["notes"])
app.include_router(memory.router, prefix="/api/v1", tags=["memory"])
