from __future__ import annotations

from openai import OpenAI

from app.llm.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    """Base for any provider exposing an OpenAI-compatible chat-completions API."""

    def __init__(self, *, api_key: str, base_url: str) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def _call(
        self, *, system_prompt: str, user_prompt: str, model: str, temperature: float, max_tokens: int
    ) -> tuple[str, int, int]:
        response = self._client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = response.choices[0].message.content or ""
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        return text, prompt_tokens, completion_tokens
