from __future__ import annotations

import pytest
from app.llm.base import LLMProvider
from app.llm.types import CompletionRequest, LLMSchemaValidationError, Purpose


class _AlwaysBadProvider(LLMProvider):
    name = "always-bad"

    def _call(
        self, *, system_prompt: str, user_prompt: str, model: str, temperature: float, max_tokens: int
    ) -> tuple[str, int, int]:
        return "not json", 5, 5


class _RepairsOnSecondTryProvider(LLMProvider):
    name = "repairs-second-try"

    def __init__(self) -> None:
        self._calls = 0

    def _call(
        self, *, system_prompt: str, user_prompt: str, model: str, temperature: float, max_tokens: int
    ) -> tuple[str, int, int]:
        self._calls += 1
        if self._calls == 1:
            return "not json", 5, 5
        return '{"ok": true}', 5, 5


def test_schema_validation_fails_after_one_repair_retry() -> None:
    provider = _AlwaysBadProvider()
    request = CompletionRequest(
        purpose=Purpose.EXTRACT,
        system_prompt="sys",
        user_prompt="x",
        response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )
    with pytest.raises(LLMSchemaValidationError):
        provider.complete(request, model="m")


def test_schema_validation_succeeds_on_repair_retry() -> None:
    provider = _RepairsOnSecondTryProvider()
    request = CompletionRequest(
        purpose=Purpose.EXTRACT,
        system_prompt="sys",
        user_prompt="x",
        response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )
    result = provider.complete(request, model="m")
    assert result.parsed == {"ok": True}
