"""Phase 3: the deterministic KPI engine.

Nothing in this package lets an LLM calculate, invent, or adjust a business number.
Every KPI value comes from a parameterized SQL aggregation against canonical tables
(currently only `fact_sales`); the LLM is never on the path from raw data to a KPI value.
"""
