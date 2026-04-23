from openai import OpenAI

from packages.common.config import model_config


class AliyunEmbeddingClient:
    def __init__(self) -> None:
        if not model_config.embedding_api_key:
            raise ValueError("SYNAPSE_EMBEDDING_API_KEY is not set")
        self.client = OpenAI(
            api_key=model_config.embedding_api_key,
            base_url=model_config.embedding_api_base,
        )
        self.model = model_config.embedding_model

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding
