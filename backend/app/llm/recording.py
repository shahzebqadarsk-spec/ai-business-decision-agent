"""Cost estimation and call recording. Records metadata only -- never prompts/content."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.db.models.operations import LlmCall
from app.llm.config import ModelConfig
from app.llm.types import CompletionResult, Purpose


def estimate_cost_usd(model_config: ModelConfig, *, prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens / 1000 * model_config.input_cost_per_1k
        + completion_tokens / 1000 * model_config.output_cost_per_1k
    )


class CallRecorder(Protocol):
    def record(
        self,
        *,
        purpose: Purpose,
        result: CompletionResult,
        cost_usd: float,
        success: bool,
        error_message: str | None = None,
    ) -> None: ...


class NullCallRecorder:
    def record(
        self,
        *,
        purpose: Purpose,
        result: CompletionResult,
        cost_usd: float,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        return None


class DbCallRecorder:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        purpose: Purpose,
        result: CompletionResult,
        cost_usd: float,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        self._session.add(
            LlmCall(
                provider=result.provider,
                model=result.model,
                purpose=purpose.value,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                estimated_cost_usd=cost_usd,
                latency_ms=result.latency_ms,
                success=success,
                error_message=error_message,
            )
        )
        self._session.commit()
