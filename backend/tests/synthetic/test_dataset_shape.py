from __future__ import annotations

import pandas as pd
from generator.catalog import CATEGORIES, LINES, MATERIALS, PLANTS, PRODUCTS, REGIONS, SUPPLIERS
from generator.config import GeneratorConfig
from generator.macro import months


def test_required_entities_exist(fast_dataset: dict[str, pd.DataFrame]) -> None:
    assert set(fast_dataset["regions"]["id"]) == {r.id for r in REGIONS}
    assert set(fast_dataset["categories"]["id"]) == {c.id for c in CATEGORIES}
    assert set(fast_dataset["products"]["id"]) == {p.id for p in PRODUCTS}
    assert set(fast_dataset["suppliers"]["id"]) == {s.id for s in SUPPLIERS}
    assert set(fast_dataset["materials"]["id"]) == {m.id for m in MATERIALS}
    assert set(fast_dataset["plants"]["id"]) == {p.id for p in PLANTS}
    assert set(fast_dataset["lines"]["id"]) == {line.id for line in LINES}


def test_entity_counts_match_locked_decisions() -> None:
    assert len(REGIONS) == 5
    assert len(CATEGORIES) == 4
    assert len(PRODUCTS) == 25
    assert len(SUPPLIERS) == 12
    assert len(MATERIALS) == 8
    assert len(PLANTS) == 3
    assert len(LINES) == 9


def test_customer_and_employee_counts_at_full_scale(default_dataset: dict[str, pd.DataFrame]) -> None:
    assert len(default_dataset["customers"]) == 300
    assert len(default_dataset["employees"]) == 250


def test_36_months_present_in_every_fact_table(fast_dataset: dict[str, pd.DataFrame]) -> None:
    expected = {m.isoformat() for m in months()}
    for table_name in ("sales", "procurement", "production", "inventory", "overtime", "expenses"):
        actual = set(fast_dataset[table_name]["month"])
        assert actual == expected, f"{table_name} missing months: {expected - actual}"


def test_sales_row_count_in_target_band_at_full_scale(default_dataset: dict[str, pd.DataFrame]) -> None:
    n = len(default_dataset["sales"])
    assert 150_000 <= n <= 300_000, f"sales row count {n} outside the Phase 1 target band"


def test_no_future_dates(default_dataset: dict[str, pd.DataFrame]) -> None:
    from datetime import date

    order_dates = pd.to_datetime(default_dataset["sales"]["order_date"]).dt.date
    assert (order_dates <= date(2025, 12, 31)).all()


def test_currency_is_pkr_everywhere(default_dataset: dict[str, pd.DataFrame]) -> None:
    for table_name in ("sales", "procurement", "expenses"):
        assert (default_dataset[table_name]["currency"] == "PKR").all()


def test_gross_amount_equals_quantity_times_unit_price(default_dataset: dict[str, pd.DataFrame]) -> None:
    sales = default_dataset["sales"]
    expected = (sales["quantity"] * sales["unit_price_pkr"]).round(2)
    assert ((expected - sales["gross_amount_pkr"]).abs() < 0.01).all()


def test_config_locked_values_match_dataset(fast_config: GeneratorConfig) -> None:
    assert fast_config.start_month.isoformat() == "2023-01-01"
    assert fast_config.months == 36
    assert fast_config.currency == "PKR"
