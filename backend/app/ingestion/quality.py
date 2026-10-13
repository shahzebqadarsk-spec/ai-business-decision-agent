"""Data-quality detection: missing values, duplicates, invalid dates, impossible numerics,
inconsistent categoricals, suspicious outliers, referential-integrity issues, schema
inconsistencies.

Outlier detection uses a robust IQR-based rule rather than a mean/stddev z-score
deliberately: the Phase 1 dataset's customer base is Zipf-concentrated by design (see
docs/SYNTHETIC_DATA.md), so a few customers placing legitimately large orders is expected
business behaviour, not a data-quality problem. A z-score on a right-skewed distribution
like that would flag those legitimate large orders constantly; IQR with a wide (3x) whisker
multiplier only flags values well outside even that skew.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

_OUTLIER_IQR_MULTIPLIER = 3.0
_NUMERIC_COLUMNS_THAT_MUST_BE_POSITIVE = ("quantity", "unit_price", "net_amount", "gross_amount")
_CATEGORICAL_CASE_VARIANT_COLUMNS = ("payment_terms",)


@dataclass
class QualityIssue:
    issue_type: str
    severity: str
    description: str
    column_name: str | None = None
    affected_row_count: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


def _check_missing_values(df: pd.DataFrame) -> list[QualityIssue]:
    issues = []
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            issues.append(
                QualityIssue(
                    issue_type="missing_values",
                    severity="warning" if null_count / len(df) < 0.1 else "error",
                    column_name=col,
                    description=f"{null_count} missing value(s) in column '{col}'.",
                    affected_row_count=null_count,
                )
            )
    return issues


def _check_duplicates(df: pd.DataFrame) -> list[QualityIssue]:
    duplicate_count = int(df.duplicated().sum())
    if duplicate_count == 0:
        return []
    return [
        QualityIssue(
            issue_type="duplicate_records",
            severity="warning",
            description=f"{duplicate_count} fully duplicated row(s) found.",
            affected_row_count=duplicate_count,
        )
    ]


def _check_invalid_dates(df: pd.DataFrame, date_columns: tuple[str, ...]) -> list[QualityIssue]:
    issues = []
    for col in date_columns:
        if col not in df.columns:
            continue
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue
        parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
        invalid_count = int(parsed.isna().sum())
        if invalid_count > 0:
            issues.append(
                QualityIssue(
                    issue_type="invalid_dates",
                    severity="error",
                    column_name=col,
                    description=f"{invalid_count} value(s) in '{col}' could not be parsed as dates.",
                    affected_row_count=invalid_count,
                )
            )
    return issues


def _check_impossible_numeric_values(df: pd.DataFrame) -> list[QualityIssue]:
    issues = []
    for col in _NUMERIC_COLUMNS_THAT_MUST_BE_POSITIVE:
        if col not in df.columns:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        bad_count = int((numeric <= 0).sum())
        if bad_count > 0:
            issues.append(
                QualityIssue(
                    issue_type="impossible_numeric_values",
                    severity="error",
                    column_name=col,
                    description=f"{bad_count} non-positive value(s) found in '{col}'.",
                    affected_row_count=bad_count,
                )
            )
    return issues


def _check_inconsistent_categorical_values(df: pd.DataFrame) -> list[QualityIssue]:
    issues = []
    for col in _CATEGORICAL_CASE_VARIANT_COLUMNS:
        if col not in df.columns:
            continue
        non_null = df[col].dropna().astype(str)
        if len(non_null) == 0:
            continue
        raw_unique = non_null.nunique()
        normalized_unique = non_null.str.lower().str.replace(r"[\s_-]", "", regex=True).nunique()
        if raw_unique > normalized_unique:
            issues.append(
                QualityIssue(
                    issue_type="inconsistent_categorical_values",
                    severity="warning",
                    column_name=col,
                    description=(
                        f"'{col}' has {raw_unique} distinct raw values but only "
                        f"{normalized_unique} after normalising case/spacing -- likely "
                        "inconsistent formatting of the same underlying categories."
                    ),
                )
            )
    return issues


def _check_suspicious_outliers(df: pd.DataFrame, measure_columns: tuple[str, ...]) -> list[QualityIssue]:
    issues = []
    for col in measure_columns:
        if col not in df.columns:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(numeric) < 10:
            continue
        q1, q3 = numeric.quantile([0.25, 0.75])
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower = q1 - _OUTLIER_IQR_MULTIPLIER * iqr
        upper = q3 + _OUTLIER_IQR_MULTIPLIER * iqr
        outlier_count = int(((numeric < lower) | (numeric > upper)).sum())
        if outlier_count > 0:
            issues.append(
                QualityIssue(
                    issue_type="suspicious_outliers",
                    severity="warning",
                    column_name=col,
                    description=(
                        f"{outlier_count} value(s) in '{col}' fall outside "
                        f"[{lower:.2f}, {upper:.2f}] (robust IQR bounds)."
                    ),
                    affected_row_count=outlier_count,
                )
            )
    return issues


def _check_referential_integrity(
    df: pd.DataFrame, known_ids_by_column: dict[str, set[str]]
) -> list[QualityIssue]:
    issues = []
    for col, known_ids in known_ids_by_column.items():
        if col not in df.columns or not known_ids:
            continue
        non_null = df[col].dropna().astype(str)
        orphans = non_null[~non_null.isin(known_ids)]
        if len(orphans) > 0:
            issues.append(
                QualityIssue(
                    issue_type="referential_integrity",
                    severity="error",
                    column_name=col,
                    description=(
                        f"{len(orphans)} value(s) in '{col}' do not match any known "
                        f"record (e.g. {orphans.unique()[0]!r})."
                    ),
                    affected_row_count=len(orphans),
                )
            )
    return issues


def _check_schema_inconsistency(
    df: pd.DataFrame, reference_columns: tuple[str, ...] | None
) -> list[QualityIssue]:
    if not reference_columns:
        return []
    current = set(df.columns)
    reference = set(reference_columns)
    missing = reference - current
    extra = current - reference
    if not missing and not extra:
        return []
    return [
        QualityIssue(
            issue_type="schema_inconsistency",
            severity="warning",
            description=(
                f"Column set differs from the reference schema for this dataset. "
                f"Missing: {sorted(missing) or 'none'}; unexpected: {sorted(extra) or 'none'}."
            ),
            details={"missing": sorted(missing), "extra": sorted(extra)},
        )
    ]


def run_quality_checks(
    df: pd.DataFrame,
    *,
    date_columns: tuple[str, ...] = ("order_date", "invoice_date", "due_date", "month"),
    measure_columns: tuple[str, ...] = (
        "quantity",
        "unit_price",
        "net_amount",
        "gross_amount",
    ),
    known_ids_by_column: dict[str, set[str]] | None = None,
    reference_columns: tuple[str, ...] | None = None,
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    issues.extend(_check_missing_values(df))
    issues.extend(_check_duplicates(df))
    issues.extend(_check_invalid_dates(df, date_columns))
    issues.extend(_check_impossible_numeric_values(df))
    issues.extend(_check_inconsistent_categorical_values(df))
    issues.extend(_check_suspicious_outliers(df, measure_columns))
    issues.extend(_check_referential_integrity(df, known_ids_by_column or {}))
    issues.extend(_check_schema_inconsistency(df, reference_columns))
    return issues
