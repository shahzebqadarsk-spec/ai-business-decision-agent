from __future__ import annotations

import pandas as pd
from generator.assemble import assemble_dataset
from generator.config import GeneratorConfig
from generator.rng import make_streams


def _build(seed: int, scale: float = 0.05) -> dict[str, pd.DataFrame]:
    config = GeneratorConfig(seed=seed, scale=scale)
    return assemble_dataset(config, make_streams(config.seed))


def test_same_seed_produces_identical_sales_table() -> None:
    first = _build(seed=123)
    second = _build(seed=123)
    pd.testing.assert_frame_equal(first["sales"], second["sales"])


def test_same_seed_produces_identical_ground_truth_inputs() -> None:
    first = _build(seed=123)
    second = _build(seed=123)
    for table in ("procurement", "overtime", "inventory"):
        pd.testing.assert_frame_equal(first[table], second[table])


def test_different_seeds_produce_different_sales_tables() -> None:
    first = _build(seed=123)
    second = _build(seed=456)
    assert not first["sales"]["quantity"].equals(second["sales"]["quantity"])


def test_fast_and_default_configs_share_the_same_entity_universe(
    fast_dataset: dict[str, pd.DataFrame], default_dataset: dict[str, pd.DataFrame]
) -> None:
    # scale changes *how many* customers/employees exist and their behaviour, never the
    # static catalog (regions/categories/products/suppliers/materials/plants/lines).
    for table_name in ("regions", "categories", "products", "suppliers", "materials", "plants", "lines"):
        assert set(fast_dataset[table_name]["id"]) == set(default_dataset[table_name]["id"])
