from __future__ import annotations

from pathlib import Path

import pytest
from generator.config import GeneratorConfig
from generator.pipeline import generate


@pytest.fixture(scope="session")
def generated_output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A real (small-scale) Phase 1 generator run, clean + messy, used to prove the
    ingestion pipeline against actual generator output rather than hand-written fixtures."""
    output_dir = tmp_path_factory.mktemp("phase2_fixture") / "output"
    config = GeneratorConfig(seed=42, scale=0.1)
    generate(config, output_dir)
    return output_dir


@pytest.fixture(scope="session")
def clean_sales_csv(generated_output_dir: Path) -> Path:
    return generated_output_dir / "clean" / "sales.csv"


@pytest.fixture(scope="session")
def messy_sales_csv(generated_output_dir: Path) -> Path:
    return generated_output_dir / "messy" / "sales.csv"
