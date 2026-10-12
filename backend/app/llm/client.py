from __future__ import annotations

from app.llm.base import LLMProvider
from app.llm.config import ModelConfig
from app.llm.recording import CallRecorder, estimate_cost_usd
from app.llm.types import CompletionRequest, CompletionResult, LLMSchemaValidationError, Purpose


class LLMClient:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        purpose: Purpose,
        recorder: CallRecorder,
        cost_model: ModelConfig | None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._purpose = purpose
        self._recorder = recorder
        self._cost_model = cost_model

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, object] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> CompletionResult:
        request = CompletionRequest(
            purpose=self._purpose,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            result = self._provider.complete(request, model=self._model)
        except LLMSchemaValidationError as exc:
            self._recorder.record(
                purpose=self._purpose,
                result=CompletionResult(text="", provider=self._provider.name, model=self._model),
                cost_usd=0.0,
                success=False,
                error_message=str(exc),
            )
            raise
        cost = (
            estimate_cost_usd(
                self._cost_model,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
            )
            if self._cost_model is not None
            else 0.0
        )
        self._recorder.record(purpose=self._purpose, result=result, cost_usd=cost, success=True)
        return result
