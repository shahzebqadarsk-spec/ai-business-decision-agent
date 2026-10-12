"""Verifies each of the 5 planted problems is independently recoverable from the written
(default scale=1.0, seed=42) output tables, landing in the band documented in DECISIONS.md.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from generator.config import GeneratorConfig
from generator.macro import cpi_index, months
from generator.measure import (
    measure_inventory_imbalance,
    measure_margin_decline,
    measure_overtime_rise,
    measure_procurement_increase,
    measure_region_decline,
)


def _band(ground_truth: dict[str, Any], issue_id: str) -> tuple[float, float]:
    issue = next(i for i in ground_truth["issues"] if i["id"] == issue_id)
    low, high = issue["expected_magnitude_range"]
    return float(low), float(high)


def test_gt01_procurement_increase_in_band(
    default_dataset: dict[str, pd.DataFrame], default_config: GeneratorConfig, default_ground_truth: Any
) -> None:
    cpi_by_month = {m.isoformat(): v for m, v in cpi_index(months()).items()}
    value = measure_procurement_increase(
        default_dataset["procurement"],
        supplier_id=default_config.planted.procurement_supplier_id,
        material_id=default_config.planted.procurement_material_id,
        cpi_by_month=cpi_by_month,
    )
    low, high = _band(default_ground_truth, "GT-01")
    assert low <= value <= high


def test_gt01_undeflated_measurement_overshoots_the_planted_effect(
    default_dataset: dict[str, pd.DataFrame], default_config: GeneratorConfig
) -> None:
    """Regression test for the CPI-deflation fix: without deflating by CPI, the measured
    increase conflates the planted ~17% supplier-specific effect with macro inflation and
    comes out materially higher than the deflated (correct) measurement."""
    deflated = measure_procurement_increase(
        default_dataset["procurement"],
        supplier_id=default_config.planted.procurement_supplier_id,
        material_id=default_config.planted.procurement_material_id,
        cpi_by_month={m.isoformat(): v for m, v in cpi_index(months()).items()},
    )
    undeflated = measure_procurement_increase(
        default_dataset["procurement"],
        supplier_id=default_config.planted.procurement_supplier_id,
        material_id=default_config.planted.procurement_material_id,
        cpi_by_month=None,
    )
    assert undeflated > deflated


def test_gt02_region_decline_in_band(
    default_dataset: pd.DataFrame, default_config: GeneratorConfig, default_ground_truth: Any
) -> None:
    value = measure_region_decline(
        default_dataset["sales"], region_id=default_config.planted.region_decline_id
    )
    low, high = _band(default_ground_truth, "GT-02")
    assert low <= value <= high
    assert value < 0, "GT-02 must be a decline"


def test_gt03_margin_decline_in_band(
    default_dataset: pd.DataFrame, default_config: GeneratorConfig, default_ground_truth: Any
) -> None:
    value = measure_margin_decline(
        default_dataset["sales"], product_id=default_config.planted.margin_decline_product_id
    )
    low, high = _band(default_ground_truth, "GT-03")
    assert low <= value <= high
    assert value > 0, "GT-03 must be a margin-percentage-point deterioration"


def test_gt04_overtime_rise_in_band(
    default_dataset: pd.DataFrame, default_config: GeneratorConfig, default_ground_truth: Any
) -> None:
    value = measure_overtime_rise(
        default_dataset["overtime"], line_id=default_config.planted.overtime_line_id
    )
    low, high = _band(default_ground_truth, "GT-04")
    assert low <= value <= high


def test_gt04_overtime_is_near_zero_in_year_one(
    default_dataset: pd.DataFrame, default_config: GeneratorConfig
) -> None:
    overtime = default_dataset["overtime"]
    subset = overtime[
        (overtime["line_id"] == default_config.planted.overtime_line_id)
        & (overtime["month"].isin(["2023-01-01", "2023-02-01", "2023-03-01"]))
    ]
    assert subset["overtime_hours"].mean() < 50.0


def test_gt05_inventory_imbalance_in_band(
    default_dataset: pd.DataFrame, default_config: GeneratorConfig, default_ground_truth: Any
) -> None:
    value = measure_inventory_imbalance(
        default_dataset["inventory"], product_id=default_config.planted.inventory_imbalance_product_id
    )
    low, high = _band(default_ground_truth, "GT-05")
    assert low <= value <= high
