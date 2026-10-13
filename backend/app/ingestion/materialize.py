"""Canonical materialization: confirmed mappings + raw rows -> typed `FactSales` rows,
with row-level lineage. Only ever runs on *confirmed* mappings -- a rejected or still-
unresolved mapping for a required field blocks materialization outright rather than being
silently skipped or auto-accepted.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

import pandas as pd

from app.db.models.canonical import FactSales
from app.fx.convert import fx_rate
from app.fx.rates import RATES_AS_OF
from app.ingestion.canonical_fields import required_fields
from app.ingestion.numeric_format import clean_numeric_string, detect_currency_code

_DATE_FIELDS = ("month", "order_date", "invoice_date")
_NUMERIC_FIELDS = (
    "quantity",
    "unit_price",
    "gross_amount",
    "net_amount",
    "cogs_amount",
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

    for money_field in ("unit_price", "net_amount", "cogs_amount"):
        money_column = column_for_field.get(money_field, "")
        if not money_column:
            continue
        detected = detect_currency_code(raw_row.get(money_column))
        if detected:
            return detected

    return reporting_currency


def detect_dominant_currency(df: pd.DataFrame, confirmed_mapping: dict[str, str]) -> str | None:
    """A client's `reporting_currency` is resolved once, from its own very first upload --
    never guessed from outside the data, and never defaulted to PKR just because that used to
    be the only deployment-wide setting (Phase 9). This tallies the same per-row signals
    `_resolve_native_currency` uses (a confirmed `currency` column value, else a symbol/code
    detected in a money cell) across every row of the upload and returns whichever code is
    most common -- or `None` if the upload gives no currency signal at all, leaving the caller
    to fall back to the deployment's configured default for that one, signal-less case only.
    """
    column_for_field = {canonical: source for source, canonical in confirmed_mapping.items()}
    currency_column = column_for_field.get("currency", "")
    money_columns = [
        column_for_field[field]
        for field in ("unit_price", "net_amount", "cogs_amount")
        if column_for_field.get(field)
    ]

    counts: Counter[str] = Counter()
    for raw_row in df.to_dict(orient="records"):
        if currency_column:
            mapped_value = raw_row.get(currency_column)
            if isinstance(mapped_value, str) and mapped_value.strip():
                counts[mapped_value.strip().upper()] += 1
                continue
        for money_column in money_columns:
            detected = detect_currency_code(raw_row.get(money_column))
            if detected:
                counts[detected] += 1
                break

    if not counts:
        return None
    return counts.most_common(1)[0][0]


def materialize_fact_sales(
    df: pd.DataFrame,
    *,
    confirmed_mapping: dict[str, str],
    source_file_id: UUID,
    client_id: UUID | str | None,
    reporting_currency: str,
) -> tuple[list[FactSales], MaterializationResult]:
    """`confirmed_mapping` is {source_column: canonical_field}, confirmed mappings only.
    `reporting_currency` is the target currency every row's money fields get converted into --
    resolved by the caller (the client's own auto-detected currency, or the deployment default
    for a client whose first upload gave no signal) rather than read from global settings here,
    so two clients materializing concurrently never contend over one shared setting.
    """
    missing = tuple(f for f in required_fields("fact_sales") if f not in confirmed_mapping.values())
    if missing:
        raise MissingRequiredFieldMappingError(missing)

    column_for_field = {canonical: source for source, canonical in confirmed_mapping.items()}

    rows: list[FactSales] = []
    skipped = 0
    skipped_reasons: list[str] = []

    for row_number, raw_row in enumerate(df.to_dict(orient="records")):
        try:
            month = _coerce_date(raw_row.get(column_for_field.get("month", "")))
            customer_id = raw_row.get(column_for_field.get("customer_id", ""))
            product_id = raw_row.get(column_for_field.get("product_id", ""))
            quantity = _coerce_numeric(raw_row.get(column_for_field.get("quantity", "")))
            unit_price = _coerce_numeric(raw_row.get(column_for_field.get("unit_price", "")))
            net_amount = _coerce_numeric(raw_row.get(column_for_field.get("net_amount", "")))
            cogs_amount = _coerce_numeric(raw_row.get(column_for_field.get("cogs_amount", "")))

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
                client_id=client_id,
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
                unit_price=unit_price,
                gross_amount=_coerce_numeric(raw_row.get(column_for_field.get("gross_amount", ""))),
                net_amount=net_amount,
                cogs_amount=cogs_amount,
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
