from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from generator.config import GeneratorConfig
from generator.pipeline import generate


def test_messy_sales_has_more_rows_than_clean(
    fast_dataset: dict[str, pd.DataFrame], fast_messy: tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]
) -> None:
    messy_tables, _defects = fast_messy
    assert len(messy_tables["sales"]) > len(fast_dataset["sales"])


def test_messy_sales_has_missing_values(
    fast_messy: tuple[dict[str, pd.DataFrame], list[dict[str, Any]]],
) -> None:
    messy_tables, _defects = fast_messy
    assert messy_tables["sales"]["discount_pct"].isna().any()


def test_messy_sales_has_impossible_numeric_values(
    fast_messy: tuple[dict[str, pd.DataFrame], list[dict[str, Any]]],
) -> None:
    messy_tables, _defects = fast_messy
    sales = messy_tables["sales"]
    assert (sales["quantity"] < 0).any() or (sales["unit_price_pkr"] == 0).any()


def test_messy_sales_has_orphan_customer_ids(
    fast_dataset: dict[str, pd.DataFrame], fast_messy: tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]
) -> None:
    messy_tables, _defects = fast_messy
    known_customers = set(fast_dataset["customers"]["id"])
    assert (~messy_tables["sales"]["customer_id"].isin(known_customers)).any()


def test_messy_sales_has_schema_inconsistency(
    fast_messy: tuple[dict[str, pd.DataFrame], list[dict[str, Any]]],
) -> None:
    messy_tables, _defects = fast_messy
    assert "net_amount" in messy_tables["sales"].columns
    assert "net_amount_pkr" not in messy_tables["sales"].columns


def test_defects_manifest_documents_every_injected_defect(
    fast_messy: tuple[dict[str, pd.DataFrame], list[dict[str, Any]]],
) -> None:
    _messy_tables, defects = fast_messy
    defect_types = {d["type"] for d in defects}
    assert {
        "missing_values",
        "duplicate_records",
        "invalid_dates",
        "impossible_numeric_values",
        "inconsistent_categorical_values",
        "suspicious_outliers",
        "referential_integrity",
        "schema_inconsistency",
    }.issubset(defect_types)


def test_no_messy_flag_skips_messy_output(tmp_path: Path) -> None:
    config = GeneratorConfig(seed=42, scale=0.05, write_messy=False)
    result = generate(config, tmp_path / "output")
    assert result["wrote_messy"] is False
    assert not (tmp_path / "output" / "messy").exists()
    assert not (tmp_path / "output" / "_hidden" / "messy_defects.yaml").exists()
    assert (tmp_path / "output" / "_hidden" / "ground_truth.yaml").exists()


def test_messy_flag_writes_messy_output(tmp_path: Path) -> None:
    config = GeneratorConfig(seed=42, scale=0.05, write_messy=True)
    result = generate(config, tmp_path / "output")
    assert result["wrote_messy"] is True
    assert (tmp_path / "output" / "messy" / "sales.csv").exists()
    assert (tmp_path / "output" / "_hidden" / "messy_defects.yaml").exists()
