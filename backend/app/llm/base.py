"""Template-method base provider: schema injection + one repair retry."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod

from app.llm.types import CompletionRequest, CompletionResult, LLMSchemaValidationError


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def _call(
        self, *, system_prompt: str, user_prompt: str, model: str, temperature: float, max_tokens: int
    ) -> tuple[str, int, int]:
        """Return (raw_text, prompt_tokens, completion_tokens)."""

    def complete(self, request: CompletionRequest, *, model: str) -> CompletionResult:
        start = time.monotonic()
        system_prompt = request.system_prompt
        if request.response_schema is not None:
            system_prompt += (
                f"\n\nRespond with JSON only, matching this schema:\n{json.dumps(request.response_schema)}"
            )

        raw, prompt_tokens, completion_tokens = self._call(
            system_prompt=system_prompt,
            user_prompt=request.user_prompt,
            model=model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        parsed = self._try_parse(raw, request)
        if request.response_schema is not None and parsed is None:
            # one repair retry: ask the model to fix its own output
            repair_prompt = (
                f"Your previous response was not valid JSON for the required schema.\n"
                f"Previous response:\n{raw}\n\nReturn ONLY corrected JSON matching the schema."
            )
            raw, extra_prompt, extra_completion = self._call(
                system_prompt=system_prompt,
                user_prompt=repair_prompt,
                model=model,
                temperature=0.0,
                max_tokens=request.max_tokens,
            )
            prompt_tokens += extra_prompt
            completion_tokens += extra_completion
            parsed = self._try_parse(raw, request)
            if parsed is None:
                raise LLMSchemaValidationError(
                    f"Provider {self.name!r} failed to produce schema-valid JSON after one repair retry."
                )

        latency_ms = int((time.monotonic() - start) * 1000)
        return CompletionResult(
            text=raw,
            parsed=parsed,
            provider=self.name,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _try_parse(raw: str, request: CompletionRequest) -> dict[str, object] | None:
        if request.response_schema is None:
            return None
        try:
            parsed: dict[str, object] = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed
