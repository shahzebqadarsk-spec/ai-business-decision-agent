from __future__ import annotations

import pytest
from app.llm.config import RoutingConfig
from app.llm.router import LLMRouter
from app.llm.types import Purpose


@pytest.fixture
def routing_config() -> RoutingConfig:
    from pathlib import Path

    return RoutingConfig.load(Path(__file__).resolve().parents[2] / "config" / "llm_routing.yaml")


def test_router_uses_mock_when_configured(routing_config: RoutingConfig) -> None:
    router = LLMRouter(routing=routing_config, use_mock=True, deepseek_api_key=None)
    client = router.client_for(Purpose.CLASSIFY)
    result = client.complete(system_prompt="sys", user_prompt="hello")
    assert result.provider == "mock"


def test_router_raises_without_api_key_when_not_mock(routing_config: RoutingConfig) -> None:
    router = LLMRouter(routing=routing_config, use_mock=False, deepseek_api_key=None)
    with pytest.raises(RuntimeError):
        router.client_for(Purpose.CLASSIFY)


def test_describe_never_leaks_key(routing_config: RoutingConfig) -> None:
    router = LLMRouter(routing=routing_config, use_mock=False, deepseek_api_key="secret-key")
    description = router.describe()
    assert "secret-key" not in str(description)
    assert description["deepseek_key_present"] is True


def test_all_purposes_have_a_route(routing_config: RoutingConfig) -> None:
    for purpose in Purpose:
        routing_config.resolve(purpose)  # should not raise
