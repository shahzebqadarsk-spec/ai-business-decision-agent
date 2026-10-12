"""Phase 3 KPI tests run against the *real* seed-42 synthetic dataset materialized into
`fact_sales`. The fixtures that load it (`seeded_fact_sales_file_id`, `sales_df`,
`planted_config`, `full_scale_sales_csv`) live in the root `tests/conftest.py` now, shared with
Phase 4's `tests/rca/` suite -- both need the real, full dataset, and sharing one session-scoped
load avoids paying for (and wiping) it twice. Nothing left to define here.
"""
