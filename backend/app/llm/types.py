from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class Purpose(StrEnum):
    CLASSIFY = "classify"
    EXTRACT = "extract"
    SUMMARISE = "summarise"
    NARRATE_ANALYSIS = "narrate_analysis"
    STRATEGIC_REASONING = "strategic_reasoning"
    VERIFY = "verify"


class CompletionRequest(BaseModel):
    purpose: Purpose
    system_prompt: str
    user_prompt: str
    response_schema: dict[str, Any] | None = None
    temperature: float = 0.2
    max_tokens: int = 1024


class CompletionResult(BaseModel):
    text: str
    parsed: dict[str, Any] | None = None
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


class LLMSchemaValidationError(RuntimeError):
    """Raised when a provider's structured output fails schema validation twice."""
