"""Phase 4: deterministic issue detection + root-cause / driver analysis + evidence.

Mirrors `app/kpi/`'s shape deliberately: a declarative config module (`materiality.py`,
parallel to the KPI registry), ordinary Python functions doing the math (`issues.py`,
`decomposition.py`), an orchestration layer that turns results into persisted rows
(`engine.py`, `evidence.py`). No module in this package accepts a free-form SQL string, an
expression, or anything else an LLM (or anyone else) could use to compute something outside
what these functions implement -- the same structural guarantee Phase 3 used for the KPI
engine, applied here to materiality decisions and causal-sounding claims as well as numbers.
"""
