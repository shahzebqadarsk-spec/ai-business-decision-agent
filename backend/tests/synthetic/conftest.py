from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from generator.assemble import assemble_dataset
from generator.config import GeneratorConfig
from generator.ground_truth import build_ground_truth
from generator.messy import build_messy_dataset
from generator.pipeline import generate
from generator.rng import make_streams


@pytest.fixture(scope="session")
def fast_config() -> GeneratorConfig:
    return GeneratorConfig(seed=42, scale=0.05)


@pytest.fixture(scope="session")
def fast_dataset(fast_config: GeneratorConfig) -> dict[str, pd.DataFrame]:
    streams = make_streams(fast_config.seed)
    return assemble_dataset(fast_config, streams)


@pytest.fixture(scope="session")
def fast_ground_truth(fast_config: GeneratorConfig, fast_dataset: dict[str, pd.DataFrame]) -> dict[str, Any]:
    return build_ground_truth(fast_config, fast_dataset)


@pytest.fixture(scope="session")
def fast_messy(
    fast_config: GeneratorConfig, fast_dataset: dict[str, pd.DataFrame]
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    streams = make_streams(fast_config.seed)
    return build_messy_dataset(fast_config, fast_dataset, streams.stream("messy.defects"))


@pytest.fixture(scope="session")
def default_config() -> GeneratorConfig:
    return GeneratorConfig(seed=42, scale=1.0)


@pytest.fixture(scope="session")
def default_dataset(default_config: GeneratorConfig) -> dict[str, pd.DataFrame]:
    streams = make_streams(default_config.seed)
    return assemble_dataset(default_config, streams)


@pytest.fixture(scope="session")
def default_ground_truth(
    default_config: GeneratorConfig, default_dataset: dict[str, pd.DataFrame]
) -> dict[str, Any]:
    return build_ground_truth(default_config, default_dataset)


@pytest.fixture
def written_fast_dataset(tmp_path: Path, fast_config: GeneratorConfig) -> dict[str, Any]:
    output_dir = tmp_path / "output"
    result = generate(fast_config, output_dir)
    return {"output_dir": output_dir, "result": result}
