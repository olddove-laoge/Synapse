from pathlib import Path

from llama_cloud import LlamaCloud

from packages.common.config import app_config


class LlamaParseAdapter:
    def __init__(self) -> None:
        if not app_config.llamaparse_api_key:
            raise ValueError("SYNAPSE_LLAMAPARSE_API_KEY is not set")
        self.client = LlamaCloud(api_key=app_config.llamaparse_api_key)

    def parse_to_markdown(self, file_path: str) -> str:
        upload = self.client.files.create(file=file_path, purpose="parse")
        result = self.client.parsing.parse(
            file_id=upload.id,
            tier=app_config.llamaparse_mode,
            version="latest",
            expand=["markdown"],
        )
        pages = getattr(getattr(result, "markdown", None), "pages", [])
        markdown_chunks = [page.markdown for page in pages if getattr(page, "markdown", "").strip()]
        return "\n\n---\n\n".join(markdown_chunks).strip()

    @staticmethod
    def should_use_llamaparse(filename: str) -> bool:
        suffix = Path(filename).suffix.lower()
        return suffix in {".pdf", ".docx"}
