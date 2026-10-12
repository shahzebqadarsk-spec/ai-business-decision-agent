from __future__ import annotations

from app.llm.providers.mock import MockProvider
from app.llm.types import CompletionRequest, Purpose


def test_mock_provider_returns_text_without_schema() -> None:
    provider = MockProvider()
    request = CompletionRequest(purpose=Purpose.SUMMARISE, system_prompt="sys", user_prompt="hello world")
    result = provider.complete(request, model="mock-model")
    assert result.provider == "mock"
    assert result.parsed is None
    assert "hello world" in result.text


def test_mock_provider_returns_schema_shaped_json() -> None:
    provider = MockProvider()
    schema = {"type": "object", "properties": {"label": {"type": "string"}, "score": {"type": "number"}}}
    request = CompletionRequest(
        purpose=Purpose.CLASSIFY, system_prompt="sys", user_prompt="x", response_schema=schema
    )
    result = provider.complete(request, model="mock-model")
    assert result.parsed == {"label": "mock", "score": 0.0}
