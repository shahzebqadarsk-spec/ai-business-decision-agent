"""Canonical materialization: confirmed mappings + raw rows -> typed `FactSales` rows,
with row-level lineage. Only ever runs on *confirmed* mappings -- a rejected or still-
unresolved mapping for a required field blocks materialization outright rather than being
silently skipped or auto-accepted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

import pandas as pd

from app.config import get_settings
from app.db.models.canonical import FactSales
from app.fx.convert import fx_rate
from app.fx.rates import RATES_AS_OF
from app.ingestion.canonical_fields import required_fields
from app.ingestion.numeric_format import clean_numeric_string, detect_currency_code

_DATE_FIELDS = ("month", "order_date", "invoice_date")
_NUMERIC_FIELDS = (
    "quantity",
    "unit_price_pkr",
    "gross_amount_pkr",
    "net_amount_pkr",
    "cogs_amount_pkr",
    "gross_margin_pct",
    "discount_pct",
)


@dataclass
class MaterializationResult:
    rows_written: int
    rows_skipped: int
    skipped_reasons: list[str] = field(default_factory=list)


class MissingRequiredFieldMappingError(RuntimeError):
    def __init__(self, missing_fields: tuple[str, ...]) -> None:
        self.missing_fields = missing_fields
        super().__init__(
            f"Cannot materialize: no *confirmed* mapping for required field(s): {missing_fields}. "
            "A low-confidence or rejected mapping never materializes silently."
        )


def _coerce_date(value: str | None) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    parsed = pd.to_datetime(value, errors="coerce", format="mixed")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _coerce_numeric(value: str | None) -> float | None:
    if value is None:
        return None
    # Strip currency symbols/thousands separators (e.g. "Rs 1,441.26") before
    # parsing -- matches profiling.py's _try_numeric so a column that profiles
    # as numeric also materializes as numeric, instead of silently failing
    # here on the exact formatting that made it look numeric in the first place.
    parsed = pd.to_numeric(clean_numeric_string(value), errors="coerce")
    if pd.isna(parsed):
        return None
    return float(parsed)


def _resolve_native_currency(
    raw_row: dict[str, object],
    column_for_field: dict[str, str],
    *,
    reporting_currency: str,
) -> str:
    """Which currency this row's money fields are actually in, resolved without ever
    guessing beyond what the row itself says (Phase 8, see docs/DECISIONS.md):
      1. A confirmed `currency` column mapping, if the cell actually has a value.
      2. A currency symbol/code detected directly in a price cell's own text
         (only when unambiguous -- see numeric_format.detect_currency_code).
      3. The deployment's configured reporting currency, as the same implicit
         single-currency assumption every upload made before Phase 8 existed.
    """
    currency_column = column_for_field.get("currency", "")
    if currency_column:
        mapped_value = raw_row.get(currency_column)
        if isinstance(mapped_value, str) and mapped_value.strip():
            return mapped_value.strip().upper()

    for money_field in ("unit_price_pkr", "net_amount_pkr", "cogs_amount_pkr"):
        money_column = column_for_field.get(money_field, "")
        if not money_column:
            continue
        detected = detect_currency_code(raw_row.get(money_column))
        if detected:
            return detected

    return reporting_currency


def materialize_fact_sales(
    df: pd.DataFrame,
    *,
    confirmed_mapping: dict[str, str],
    source_file_id: UUID,
) -> tuple[list[FactSales], MaterializationResult]:
    """`confirmed_mapping` is {source_column: canonical_field}, confirmed mappings only."""
    missing = tuple(f for f in required_fields("fact_sales") if f not in confirmed_mapping.values())
    if missing:
        raise MissingRequiredFieldMappingError(missing)

    column_for_field = {canonical: source for source, canonical in confirmed_mapping.items()}
    reporting_currency = get_settings().reporting_currency

    rows: list[FactSales] = []
    skipped = 0
    skipped_reasons: list[str] = []

    for row_number, raw_row in enumerate(df.to_dict(orient="records")):
        try:
            month = _coerce_date(raw_row.get(column_for_field.get("month", "")))
            customer_id = raw_row.get(column_for_field.get("customer_id", ""))
            product_id = raw_row.get(column_for_field.get("product_id", ""))
            quantity = _coerce_numeric(raw_row.get(column_for_field.get("quantity", "")))
            unit_price = _coerce_numeric(raw_row.get(column_for_field.get("unit_price_pkr", "")))
            net_amount = _coerce_numeric(raw_row.get(column_for_field.get("net_amount_pkr", "")))
            cogs_amount = _coerce_numeric(raw_row.get(column_for_field.get("cogs_amount_pkr", "")))

            if month is None or not customer_id or not product_id:
                raise ValueError("missing a required field value")
            if quantity is None or unit_price is None or net_amount is None:
                raise ValueError("a required numeric field did not parse")

            # Phase 8: resolve this row's native currency and convert into the
            # deployment's reporting currency. Raises (ValueError subclass) and the row
            # is skipped, same as any other coercion failure, if an *explicitly mapped*
            # currency column holds a code with no known rate -- never silently guessed.
            native_currency = _resolve_native_currency(
                raw_row, column_for_field, reporting_currency=reporting_currency
            )
            rate = fx_rate(from_currency=native_currency, to_currency=reporting_currency)

            fact = FactSales(
                source_file_id=source_file_id,
                source_row_number=row_number,
                sale_id=raw_row.get(column_for_field.get("sale_id", "")),
                month=month,
                order_date=_coerce_date(raw_row.get(column_for_field.get("order_date", ""))),
                invoice_date=_coerce_date(raw_row.get(column_for_field.get("invoice_date", ""))),
                customer_id=str(customer_id),
                region_id=raw_row.get(column_for_field.get("region_id", "")),
                product_id=str(product_id),
                category_id=raw_row.get(column_for_field.get("category_id", "")),
                quantity=quantity,
                unit_price_pkr=unit_price,
                gross_amount_pkr=_coerce_numeric(raw_row.get(column_for_field.get("gross_amount_pkr", ""))),
                net_amount_pkr=net_amount,
                cogs_amount_pkr=cogs_amount,
                gross_margin_pct=_coerce_numeric(raw_row.get(column_for_field.get("gross_margin_pct", ""))),
                discount_pct=_coerce_numeric(raw_row.get(column_for_field.get("discount_pct", ""))),
                payment_terms=raw_row.get(column_for_field.get("payment_terms", "")),
                currency=native_currency,
                unit_price_reporting=unit_price * rate,
                net_amount_reporting=net_amount * rate,
                cogs_amount_reporting=cogs_amount * rate if cogs_amount is not None else None,
                fx_rate_to_reporting=rate,
                fx_rate_as_of=RATES_AS_OF,
            )
            rows.append(fact)
        except (ValueError, TypeError) as exc:
            skipped += 1
            if len(skipped_reasons) < 20:
                skipped_reasons.append(f"row {row_number}: {exc}")

    return rows, MaterializationResult(
        rows_written=len(rows), rows_skipped=skipped, skipped_reasons=skipped_reasons
    )
