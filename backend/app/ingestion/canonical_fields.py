"""The canonical schema Phase 2's semantic mapping maps *into*.

Deliberately scoped to one canonical table -- `fact_sales`, the primary business fact the
Phase 1 dataset produces -- rather than every table Phase 1 writes. This is a scope
decision (see docs/DECISIONS.md), not an oversight: it is enough to exercise the full
upload -> validate -> profile -> quality -> map -> confirm -> materialize pipeline end to
end, with real lineage, without building out a KPI engine's worth of fact/dim tables that
nothing queries yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CanonicalFieldSpec:
    name: str
    required: bool
    data_type: str  # "identifier" | "date" | "measure" | "category"
    synonyms: tuple[str, ...] = field(default_factory=tuple)


FACT_SALES_FIELDS: tuple[CanonicalFieldSpec, ...] = (
    CanonicalFieldSpec("sale_id", False, "identifier", ("id", "transaction_id", "sales_id")),
    CanonicalFieldSpec("month", True, "date", ("period", "fiscal_month")),
    CanonicalFieldSpec("order_date", False, "date", ("date", "txn_date", "sale_date")),
    CanonicalFieldSpec("invoice_date", False, "date", ()),
    CanonicalFieldSpec("customer_id", True, "identifier", ("cust_id", "client_id", "buyer_id")),
    CanonicalFieldSpec("region_id", False, "identifier", ("region", "territory", "area_id")),
    CanonicalFieldSpec("product_id", True, "identifier", ("item_id", "sku", "sku_id")),
    CanonicalFieldSpec("category_id", False, "identifier", ("category", "product_category")),
    CanonicalFieldSpec("quantity", True, "measure", ("qty", "units", "volume")),
    CanonicalFieldSpec("unit_price_pkr", True, "measure", ("unit_price", "price", "price_pkr")),
    CanonicalFieldSpec("gross_amount_pkr", False, "measure", ("gross_amount", "gross_total")),
    CanonicalFieldSpec(
        "net_amount_pkr", True, "measure", ("net_amount", "net_total", "revenue", "sales_amount")
    ),
    CanonicalFieldSpec("cogs_amount_pkr", False, "measure", ("cogs_amount", "cost_of_goods_sold")),
    CanonicalFieldSpec("gross_margin_pct", False, "measure", ("margin_pct", "gross_margin")),
    CanonicalFieldSpec("discount_pct", False, "measure", ("discount", "discount_percent")),
    CanonicalFieldSpec("payment_terms", False, "category", ("terms", "credit_terms")),
    CanonicalFieldSpec("currency", False, "category", ()),
)

CANONICAL_TABLES: dict[str, tuple[CanonicalFieldSpec, ...]] = {
    "fact_sales": FACT_SALES_FIELDS,
}


def required_fields(table: str) -> tuple[str, ...]:
    return tuple(f.name for f in CANONICAL_TABLES[table] if f.required)


def field_names(table: str) -> tuple[str, ...]:
    return tuple(f.name for f in CANONICAL_TABLES[table])
