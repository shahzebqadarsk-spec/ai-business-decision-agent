from __future__ import annotations

from app.llm.config import ModelConfig
from app.llm.recording import NullCallRecorder, estimate_cost_usd
from app.llm.types import CompletionResult, Purpose


def test_estimate_cost_usd() -> None:
    model_config = ModelConfig(model="m", input_cost_per_1k=0.001, output_cost_per_1k=0.002)
    cost = estimate_cost_usd(model_config, prompt_tokens=1000, completion_tokens=500)
    assert cost == 0.001 + 0.001


def test_null_recorder_is_a_no_op() -> None:
    recorder = NullCallRecorder()
    recorder.record(
        purpose=Purpose.CLASSIFY,
        result=CompletionResult(text="x", provider="mock", model="m"),
        cost_usd=0.0,
        success=True,
    )  # should not raise
