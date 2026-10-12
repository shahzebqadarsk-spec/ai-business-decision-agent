from __future__ import annotations

from datetime import date

import pytest
from generator.config import GeneratorConfig


def test_start_month_is_locked() -> None:
    with pytest.raises(ValueError):
        GeneratorConfig(start_month=date(2024, 1, 1))


def test_months_is_locked() -> None:
    with pytest.raises(ValueError):
        GeneratorConfig(months=24)


def test_currency_is_locked() -> None:
    with pytest.raises(ValueError):
        GeneratorConfig(currency="USD")


def test_default_seed_is_42() -> None:
    assert GeneratorConfig().seed == 42


def test_effective_sizes_scale_proportionally() -> None:
    config = GeneratorConfig(scale=0.5)
    assert config.effective_sizes.customers == 150
    assert config.effective_sizes.employees == 125


def test_effective_sizes_respect_floors_at_tiny_scale() -> None:
    config = GeneratorConfig(scale=0.01)
    assert config.effective_sizes.customers >= 15
    assert config.effective_sizes.employees >= 30
