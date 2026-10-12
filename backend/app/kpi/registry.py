"""The declarative KPI registry: one `KPIDefinition` per KPI named in the Phase 3 spec.

Deviation from the spec's literal KPI list (documented in docs/PHASE_3_KPI_ENGINE.md): "Revenue
by Region", "Revenue by Product" and "Revenue by Customer" are not separate registry entries.
They are the `revenue` KPI's dimensional breakdown (`GET .../breakdown` with dimension=region/
product/customer) -- the formula is identical (SUM(net_amount_reporting)), only the GROUP BY differs,
so a separate registry entry per dimension would just be the same formula three times over.
"""

from __future__ import annotations

from app.config import get_settings
from app.kpi import calculators as calc
from app.kpi.models import DIMENSIONS, KPICategory, KPIDefinition, KPIUnit

_SALES_DIMENSIONS = DIMENSIONS  # region, product, category, customer, month, quarter, year

# The deployment's configured reporting currency (Phase 8: multi-currency support) --
# every currency-denominated KPI is computed on *_reporting amounts, already converted
# into this currency, so this is just the display label, not a conversion target here.
_REPORTING_CURRENCY = get_settings().reporting_currency

KPI_REGISTRY: dict[str, KPIDefinition] = {}


def _register(definition: KPIDefinition) -> None:
    KPI_REGISTRY[definition.kpi_id] = definition


# --- FINANCIAL --------------------------------------------------------------------------

_register(
    KPIDefinition(
        kpi_id="revenue",
        name="Revenue",
        description="Net sales revenue: SUM(net_amount_reporting) over fact_sales for the period.",
        category=KPICategory.FINANCIAL,
        unit=KPIUnit.CURRENCY,
        currency=_REPORTING_CURRENCY,
        calculator=calc.calculate_revenue,
        required_fields=("net_amount_reporting",),
        supported_dimensions=_SALES_DIMENSIONS,
        breakdown=calc.breakdown_revenue,
    )
)

_register(
    KPIDefinition(
        kpi_id="gross_profit",
        name="Gross Profit",
        description="Revenue minus cost of goods sold: SUM(net_amount_reporting) - SUM(cogs_amount_reporting).",
        category=KPICategory.FINANCIAL,
        unit=KPIUnit.CURRENCY,
        currency=_REPORTING_CURRENCY,
        calculator=calc.calculate_gross_profit,
        required_fields=("net_amount_reporting", "cogs_amount_reporting"),
        aggregation_method="difference",
        supported_dimensions=_SALES_DIMENSIONS,
    )
)

_register(
    KPIDefinition(
        kpi_id="gross_margin_pct",
        name="Gross Margin %",
        description="Gross profit as a percentage of revenue: (Revenue - COGS) / Revenue * 100.",
        category=KPICategory.FINANCIAL,
        unit=KPIUnit.PERCENTAGE,
        calculator=calc.calculate_gross_margin_pct,
        required_fields=("net_amount_reporting", "cogs_amount_reporting"),
        aggregation_method="ratio",
    )
)

_register(
    KPIDefinition(
        kpi_id="cogs",
        name="Cost of Goods Sold",
        description="SUM(cogs_amount_reporting) over fact_sales for the period.",
        category=KPICategory.FINANCIAL,
        unit=KPIUnit.CURRENCY,
        currency=_REPORTING_CURRENCY,
        calculator=calc.calculate_cogs,
        required_fields=("cogs_amount_reporting",),
        supported_dimensions=_SALES_DIMENSIONS,
        breakdown=calc.breakdown_cogs,
    )
)

for _kpi_id, _name, _desc in (
    ("operating_expenses", "Operating Expenses", "Total operating expenses (SG&A, overhead, etc.)."),
    ("operating_profit", "Operating Profit", "Gross profit minus operating expenses."),
    ("operating_margin_pct", "Operating Margin %", "Operating profit as a percentage of revenue."),
):
    _register(
        KPIDefinition(
            kpi_id=_kpi_id,
            name=_name,
            description=_desc,
            category=KPICategory.FINANCIAL,
            unit=KPIUnit.CURRENCY if _kpi_id != "operating_margin_pct" else KPIUnit.PERCENTAGE,
            currency=_REPORTING_CURRENCY if _kpi_id != "operating_margin_pct" else None,
            calculator=calc.make_cannot_compute_calculator(("fact_expenses",)),
            required_canonical_tables=("fact_expenses",),
            implemented=False,
        )
    )

# --- SALES ------------------------------------------------------------------------------

_register(
    KPIDefinition(
        kpi_id="sales_quantity",
        name="Sales Volume / Quantity",
        description="SUM(quantity) over fact_sales for the period.",
        category=KPICategory.SALES,
        unit=KPIUnit.QUANTITY,
        calculator=calc.calculate_sales_quantity,
        required_fields=("quantity",),
        supported_dimensions=_SALES_DIMENSIONS,
        breakdown=calc.breakdown_sales_quantity,
    )
)

_register(
    KPIDefinition(
        kpi_id="average_selling_price",
        name="Average Selling Price",
        description="Revenue / Quantity for the period.",
        category=KPICategory.SALES,
        unit=KPIUnit.CURRENCY,
        currency=_REPORTING_CURRENCY,
        calculator=calc.calculate_average_selling_price,
        required_fields=("net_amount_reporting", "quantity"),
        aggregation_method="ratio",
        supported_dimensions=_SALES_DIMENSIONS,
    )
)

_register(
    KPIDefinition(
        kpi_id="customer_count",
        name="Customer Count",
        description="COUNT(DISTINCT customer_id) over fact_sales for the period.",
        category=KPICategory.SALES,
        unit=KPIUnit.COUNT,
        calculator=calc.calculate_customer_count,
        required_fields=("customer_id",),
        aggregation_method="count_distinct",
        supported_dimensions=_SALES_DIMENSIONS,
    )
)

_register(
    KPIDefinition(
        kpi_id="transaction_count",
        name="Order / Transaction Count",
        description="COUNT(DISTINCT sale_id) over fact_sales for the period.",
        category=KPICategory.SALES,
        unit=KPIUnit.COUNT,
        calculator=calc.calculate_transaction_count,
        required_fields=("sale_id",),
        aggregation_method="count_distinct",
        supported_dimensions=_SALES_DIMENSIONS,
    )
)

# --- COST (no canonical table materialized yet) ------------------------------------------

for _kpi_id, _name, _desc, _table in (
    ("procurement_cost", "Procurement Cost", "Total procurement spend.", "fact_procurement"),
    (
        "procurement_cost_per_unit",
        "Procurement Cost per Unit",
        "Procurement spend per unit of material purchased.",
        "fact_procurement",
    ),
    ("payroll_cost", "Payroll Cost", "Total payroll cost.", "fact_payroll"),
    ("overtime_cost", "Overtime Cost", "Total overtime pay.", "fact_payroll"),
    ("expense_cost", "Expense Cost", "Total general operating expense line items.", "fact_expenses"),
):
    _register(
        KPIDefinition(
            kpi_id=_kpi_id,
            name=_name,
            description=_desc,
            category=KPICategory.COST,
            unit=KPIUnit.CURRENCY,
            currency=_REPORTING_CURRENCY,
            calculator=calc.make_cannot_compute_calculator((_table,)),
            required_canonical_tables=(_table,),
            implemented=False,
        )
    )

# --- OPERATIONS (no canonical table materialized yet) -------------------------------------

for _kpi_id, _name, _desc, _unit, _table in (
    (
        "production_quantity",
        "Production Quantity",
        "Total units produced.",
        KPIUnit.QUANTITY,
        "fact_production",
    ),
    (
        "inventory_quantity",
        "Inventory Quantity",
        "Units on hand at period end.",
        KPIUnit.QUANTITY,
        "fact_inventory",
    ),
    ("inventory_value", "Inventory Value", "Value of inventory on hand.", KPIUnit.CURRENCY, "fact_inventory"),
    (
        "inventory_days",
        "Inventory Days / Days of Cover",
        "Days of inventory cover.",
        KPIUnit.DAYS,
        "fact_inventory",
    ),
    ("overtime_hours", "Overtime Hours", "Total overtime hours worked.", KPIUnit.HOURS, "fact_workforce"),
):
    _register(
        KPIDefinition(
            kpi_id=_kpi_id,
            name=_name,
            description=_desc,
            category=KPICategory.OPERATIONS,
            unit=_unit,
            currency=_REPORTING_CURRENCY if _unit == KPIUnit.CURRENCY else None,
            calculator=calc.make_cannot_compute_calculator((_table,)),
            required_canonical_tables=(_table,),
            implemented=False,
        )
    )


def get_kpi_definition(kpi_id: str) -> KPIDefinition | None:
    return KPI_REGISTRY.get(kpi_id)


def list_kpi_definitions() -> list[KPIDefinition]:
    return list(KPI_REGISTRY.values())
