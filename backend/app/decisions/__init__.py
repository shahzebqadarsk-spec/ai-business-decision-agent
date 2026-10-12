"""Phase 7: deterministic Decision Scoring.

Split into `engine.py` (the weighted multi-criteria scoring math and persistence) and
`evidence.py` (building and persisting the `Evidence` rows this phase produces), the same
split `app/forecasting/` uses and `app/scenarios/` didn't need -- unlike a scenario, a decision
score IS a claim this system is making (an advisory recommendation), so it does write Evidence,
and that formatting deserves its own module rather than living inline in the engine."""
