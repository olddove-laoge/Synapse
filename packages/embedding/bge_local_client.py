from pathlib import Path


class BGELocalEmbeddingClient:
    def __init__(self, model_path: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(self._resolve_model_path(model_path))

    @staticmethod
    def _resolve_model_path(model_path: str) -> str:
        base = Path(model_path)
        if (base / "modules.json").exists() and (base / "config_sentence_transformers.json").exists():
            return str(base)

        snapshots = base / "snapshots"
        if snapshots.exists():
            candidates = [
                p
                for p in snapshots.iterdir()
                if p.is_dir() and (p / "modules.json").exists() and (p / "config_sentence_transformers.json").exists()
            ]
            if candidates:
                newest = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
                return str(newest)

        return str(base)

    def embed(self, text: str) -> list[float]:
        vector = self.model.encode([text], normalize_embeddings=True)[0]
        return vector.tolist()
