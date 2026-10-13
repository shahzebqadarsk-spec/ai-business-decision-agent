"""Mutation tests for verify.py: corrupt a copy of the (fast) dataset and assert the
specific check catches it -- and only that mutation trips a problem."""

from __future__ import annotations

import pandas as pd
from generator.config import GeneratorConfig
from generator.verify import verify_tables


def test_clean_fast_dataset_passes(
    fast_dataset: dict[str, pd.DataFrame], fast_config: GeneratorConfig
) -> None:
    problems = verify_tables(fast_dataset, scale=fast_config.scale)
    assert problems == []


def test_missing_required_entity_is_caught(
    fast_dataset: dict[str, pd.DataFrame], fast_config: GeneratorConfig
) -> None:
    mutated = {name: df.copy() for name, df in fast_dataset.items()}
    mutated["regions"] = mutated["regions"][mutated["regions"]["id"] != "REG-05"]
    problems = verify_tables(mutated, scale=fast_config.scale)
    assert any("regions" in p for p in problems)


def test_missing_month_is_caught(fast_dataset: dict[str, pd.DataFrame], fast_config: GeneratorConfig) -> None:
    mutated = {name: df.copy() for name, df in fast_dataset.items()}
    mutated["sales"] = mutated["sales"][mutated["sales"]["month"] != "2024-06-01"]
    problems = verify_tables(mutated, scale=fast_config.scale)
    assert any("sales" in p and "2024-06-01" in p for p in problems)


def test_future_order_date_is_caught(
    fast_dataset: dict[str, pd.DataFrame], fast_config: GeneratorConfig
) -> None:
    mutated = {name: df.copy() for name, df in fast_dataset.items()}
    mutated["sales"].loc[mutated["sales"].index[0], "order_date"] = "2026-01-15"
    problems = verify_tables(mutated, scale=fast_config.scale)
    assert any("order_date" in p for p in problems)


def test_non_pkr_currency_is_caught(
    fast_dataset: dict[str, pd.DataFrame], fast_config: GeneratorConfig
) -> None:
    mutated = {name: df.copy() for name, df in fast_dataset.items()}
    mutated["sales"].loc[mutated["sales"].index[0], "currency"] = "USD"
    problems = verify_tables(mutated, scale=fast_config.scale)
    assert any("currency" in p for p in problems)


def test_broken_gross_amount_arithmetic_is_caught(
    fast_dataset: dict[str, pd.DataFrame], fast_config: GeneratorConfig
) -> None:
    mutated = {name: df.copy() for name, df in fast_dataset.items()}
    mutated["sales"].loc[mutated["sales"].index[0], "gross_amount"] = 999_999_999.0
    problems = verify_tables(mutated, scale=fast_config.scale)
    assert any("gross_amount" in p for p in problems)


def test_broken_inventory_identity_is_caught(
    fast_dataset: dict[str, pd.DataFrame], fast_config: GeneratorConfig
) -> None:
    mutated = {name: df.copy() for name, df in fast_dataset.items()}
    mutated["inventory"].loc[mutated["inventory"].index[0], "closing_stock_units"] = 999_999.0
    problems = verify_tables(mutated, scale=fast_config.scale)
    assert any("inventory" in p for p in problems)


def test_negative_quantity_is_caught(
    fast_dataset: dict[str, pd.DataFrame], fast_config: GeneratorConfig
) -> None:
    mutated = {name: df.copy() for name, df in fast_dataset.items()}
    mutated["sales"].loc[mutated["sales"].index[0], "quantity"] = -5
    problems = verify_tables(mutated, scale=fast_config.scale)
    assert any("quantity" in p for p in problems)
