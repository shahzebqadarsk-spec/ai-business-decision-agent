from __future__ import annotations

from app.llm.providers.openai_compatible import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    name = "deepseek"

    def __init__(self, *, api_key: str, base_url: str = "https://api.deepseek.com") -> None:
        super().__init__(api_key=api_key, base_url=base_url)
