"""Deterministic offline provider: no network calls, used by default and in tests."""

from __future__ import annotations

import json

from app.llm.base import LLMProvider
from app.llm.types import CompletionRequest


class MockProvider(LLMProvider):
    name = "mock"

    def complete(self, request: CompletionRequest, *, model: str) -> CompletionResult:  # type: ignore[name-defined]  # noqa: F821
        from app.llm.types import CompletionResult

        if request.response_schema is not None:
            parsed = self._mock_value_for_schema(request.response_schema)
            text = json.dumps(parsed)
        else:
            parsed = None
            text = f"[mock:{request.purpose.value}] {request.user_prompt[:200]}"
        return CompletionResult(
            text=text,
            parsed=parsed,
            provider=self.name,
            model=model,
            prompt_tokens=len(request.user_prompt.split()),
            completion_tokens=len(text.split()),
            latency_ms=1,
        )

    def _call(
        self, *, system_prompt: str, user_prompt: str, model: str, temperature: float, max_tokens: int
    ) -> tuple[str, int, int]:
        raise NotImplementedError("MockProvider overrides complete() directly.")

    @staticmethod
    def _mock_value_for_schema(schema: dict[str, object]) -> dict[str, object]:
        properties = schema.get("properties", {})
        result: dict[str, object] = {}
        if isinstance(properties, dict):
            for key, spec in properties.items():
                spec_type = spec.get("type") if isinstance(spec, dict) else None
                defaults: dict[str, object] = {
                    "string": "mock",
                    "number": 0.0,
                    "integer": 0,
                    "boolean": False,
                    "array": [],
                    "object": {},
                }
                result[key] = defaults.get(spec_type) if isinstance(spec_type, str) else None
        return result
