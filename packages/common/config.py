import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass
class ModelConfig:
    llm_provider: str = os.getenv("SYNAPSE_LLM_PROVIDER", "deepseek")
    llm_model: str = os.getenv("SYNAPSE_LLM_MODEL", "deepseek-chat")
    llm_api_base: str = os.getenv("SYNAPSE_LLM_API_BASE", "https://api.deepseek.com/v1")
    llm_api_key: str = os.getenv("SYNAPSE_LLM_API_KEY", "")

    embedding_provider: str = os.getenv("SYNAPSE_EMBEDDING_PROVIDER", "aliyun")
    embedding_model: str = os.getenv("SYNAPSE_EMBEDDING_MODEL", "text-embedding-v3")
    embedding_api_base: str = os.getenv("SYNAPSE_EMBEDDING_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    embedding_api_key: str = os.getenv("SYNAPSE_EMBEDDING_API_KEY", "")
    embedding_local_model_path: str = os.getenv(
        "SYNAPSE_EMBEDDING_LOCAL_MODEL_PATH",
        str((os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) + "/models/models--BAAI--bge-large-zh-v1.5"),
    )


@dataclass
class AppConfig:
    env: str = os.getenv("SYNAPSE_ENV", "dev")
    neo4j_uri: str = os.getenv("SYNAPSE_NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("SYNAPSE_NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("SYNAPSE_NEO4J_PASSWORD", "neo4j")
    llamaparse_api_key: str = os.getenv("SYNAPSE_LLAMAPARSE_API_KEY", "")
    llamaparse_mode: str = os.getenv("SYNAPSE_LLAMAPARSE_MODE", "agentic")


model_config = ModelConfig()
app_config = AppConfig()
