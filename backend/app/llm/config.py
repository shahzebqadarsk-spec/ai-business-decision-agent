from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from app.llm.types import Purpose


class ModelConfig(BaseModel):
    model: str
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0


class ProviderConfig(BaseModel):
    kind: str
    base_url: str | None = None
    tiers: dict[str, ModelConfig] = {}


class RoutingConfig(BaseModel):
    providers: dict[str, ProviderConfig]
    routes: dict[str, str]  # "<provider>.<tier>" keyed by Purpose value
    mock: ProviderConfig | None = None

    @classmethod
    def load(cls, path: Path) -> RoutingConfig:
        with path.open() as fh:
            raw = yaml.safe_load(fh)
        return cls.model_validate(raw)

    def resolve(self, purpose: Purpose) -> tuple[ProviderConfig, ModelConfig]:
        route = self.routes.get(purpose.value)
        if route is None:
            raise KeyError(f"No LLM route configured for purpose={purpose.value!r}")
        provider_name, tier = route.split(".", 1)
        provider = self.providers[provider_name]
        return provider, provider.tiers[tier]
