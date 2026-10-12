from __future__ import annotations

from app.llm.client import LLMClient
from app.llm.config import RoutingConfig
from app.llm.providers.deepseek import DeepSeekProvider
from app.llm.providers.mock import MockProvider
from app.llm.recording import CallRecorder, NullCallRecorder
from app.llm.types import Purpose


class LLMRouter:
    def __init__(
        self,
        *,
        routing: RoutingConfig,
        use_mock: bool,
        deepseek_api_key: str | None,
        recorder: CallRecorder | None = None,
    ) -> None:
        self._routing = routing
        self._use_mock = use_mock
        self._deepseek_api_key = deepseek_api_key
        self._recorder = recorder or NullCallRecorder()
        self._mock_provider = MockProvider()
        self._deepseek_provider: DeepSeekProvider | None = None

    def client_for(self, purpose: Purpose) -> LLMClient:
        if self._use_mock:
            return LLMClient(
                provider=self._mock_provider,
                model="mock-model",
                purpose=purpose,
                recorder=self._recorder,
                cost_model=None,
            )

        provider_config, model_config = self._routing.resolve(purpose)
        if provider_config.kind == "deepseek":
            if self._deepseek_provider is None:
                if not self._deepseek_api_key:
                    raise RuntimeError("DEEPSEEK_API_KEY is required when LLM_USE_MOCK=false.")
                self._deepseek_provider = DeepSeekProvider(
                    api_key=self._deepseek_api_key,
                    base_url=provider_config.base_url or "https://api.deepseek.com",
                )
            return LLMClient(
                provider=self._deepseek_provider,
                model=model_config.model,
                purpose=purpose,
                recorder=self._recorder,
                cost_model=model_config,
            )
        raise ValueError(f"Unsupported provider kind: {provider_config.kind!r}")

    def describe(self) -> dict[str, object]:
        return {
            "use_mock": self._use_mock,
            "deepseek_key_present": bool(self._deepseek_api_key),
            "routes": self._routing.routes,
        }
