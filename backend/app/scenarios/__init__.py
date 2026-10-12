"""Phase 6: deterministic Scenario / What-If analysis.

A single `engine.py` module is enough here, unlike `app/forecasting/`'s split into
model/backtest/sufficiency/evidence sub-modules -- there is no statistical fit to isolate (a
scenario is a plain percentage multiplier applied to an existing Phase 5 forecast) and no
Evidence to write (see `app/db/models/scenario.py`'s module docstring for why a scenario
deliberately does not produce Evidence rows)."""
