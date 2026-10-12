"""Column profiling: inferred dtype, nulls, uniqueness, samples, min/max, numeric stats,
date range, and a best-effort identifier/category/date/measure classification.

Everything here reads the DataFrame `parsing.py` produced (all-string columns) and infers
from the *values*, not from column names -- classification by name alone would just be
semantic mapping done badly twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from app.ingestion.numeric_format import clean_numeric_series

_DATE_NULL_TOLERANCE = 0.3  # a column counts as "date" if at most this fraction fails to parse
_CATEGORY_MAX_UNIQUE_RATIO = 0.05
_CATEGORY_MAX_UNIQUE_COUNT = 50


@dataclass
class ColumnProfileResult:
    column_name: str
    position: int
    inferred_dtype: str
    classification: str
    null_count: int
    null_percentage: float
    unique_count: int
    sample_values: list[str] = field(default_factory=list)
    min_value: str | None = None
    max_value: str | None = None
    mean_value: float | None = None
    stddev_value: float | None = None
    date_min: date | None = None
    date_max: date | None = None


def _try_numeric(series: pd.Series) -> pd.Series | None:
    # Strip currency symbols/thousands separators (e.g. "Rs 1,441.26") before
    # parsing -- see numeric_format.py for why this is needed, not optional.
    cleaned = clean_numeric_series(series.dropna())
    numeric = pd.to_numeric(cleaned, errors="coerce")
    if numeric.notna().mean() >= 0.95 and len(numeric.dropna()) > 0:
        return numeric
    return None


def _try_dates(series: pd.Series) -> pd.Series | None:
    non_null = series.dropna()
    if len(non_null) == 0:
        return None
    parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
    failure_rate = parsed.isna().mean()
    if failure_rate <= _DATE_NULL_TOLERANCE:
        return parsed
    return None


def profile_column(series: pd.Series, *, position: int) -> ColumnProfileResult:
    column_name = str(series.name)
    n = len(series)
    null_count = int(series.isna().sum())
    null_percentage = round(100.0 * null_count / n, 3) if n else 0.0
    non_null = series.dropna()
    unique_count = int(non_null.nunique())
    sample_values = [str(v) for v in non_null.unique()[:5]]

    numeric = _try_numeric(series)
    dates = _try_dates(series) if numeric is None else None

    if numeric is not None:
        inferred_dtype = "numeric"
        classification = "measure"
        return ColumnProfileResult(
            column_name=column_name,
            position=position,
            inferred_dtype=inferred_dtype,
            classification=classification,
            null_count=null_count,
            null_percentage=null_percentage,
            unique_count=unique_count,
            sample_values=sample_values,
            min_value=str(numeric.min()) if len(numeric) else None,
            max_value=str(numeric.max()) if len(numeric) else None,
            mean_value=float(numeric.mean()) if len(numeric) else None,
            stddev_value=float(numeric.std()) if len(numeric) > 1 else 0.0,
        )

    if dates is not None:
        return ColumnProfileResult(
            column_name=column_name,
            position=position,
            inferred_dtype="date",
            classification="date",
            null_count=null_count,
            null_percentage=null_percentage,
            unique_count=unique_count,
            sample_values=sample_values,
            min_value=str(dates.min().date()) if len(dates) else None,
            max_value=str(dates.max().date()) if len(dates) else None,
            date_min=dates.min().date() if len(dates) else None,
            date_max=dates.max().date() if len(dates) else None,
        )

    unique_ratio = unique_count / n if n else 0.0
    if unique_count <= _CATEGORY_MAX_UNIQUE_COUNT or unique_ratio <= _CATEGORY_MAX_UNIQUE_RATIO:
        classification = "category"
    elif unique_ratio > 0.8:
        classification = "identifier"
    else:
        classification = "category"

    return ColumnProfileResult(
        column_name=column_name,
        position=position,
        inferred_dtype="string",
        classification=classification,
        null_count=null_count,
        null_percentage=null_percentage,
        unique_count=unique_count,
        sample_values=sample_values,
        min_value=str(min(non_null)) if len(non_null) else None,
        max_value=str(max(non_null)) if len(non_null) else None,
    )


def profile_dataframe(df: pd.DataFrame) -> list[ColumnProfileResult]:
    return [profile_column(df[col], position=i) for i, col in enumerate(df.columns)]
