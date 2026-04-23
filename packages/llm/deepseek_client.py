from openai import OpenAI

from packages.common.config import model_config


class DeepSeekClient:
    def __init__(self) -> None:
        if not model_config.llm_api_key:
            raise ValueError("SYNAPSE_LLM_API_KEY is not set")
        self.client = OpenAI(api_key=model_config.llm_api_key, base_url=model_config.llm_api_base)
        self.model = model_config.llm_model

    def chat(self, message: str, system_prompt: str | None = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
        )
        return resp.choices[0].message.content or ""
