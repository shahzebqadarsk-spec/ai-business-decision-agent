"""Phase 5: deterministic forecasting engine.

Scoped tightly, by independent judgment (no formal spec for this phase exists -- see
`docs/PHASE_5_FORECASTING_ENGINE.md`): a single trend+seasonal model over month-granularity
history for the three metrics Phase 3's KPI engine can compute directly from `fact_sales`
(revenue, sales_quantity, cogs). Scenario/what-if analysis, decision scoring, the AI narrator,
the verifier, and chat orchestration are explicitly out of scope for this phase.
"""
