# Phase 7: Decision Scoring Engine

This document is the reference for everything Phase 7 added: the self-scoping decision that
produced it, the scoring methodology, why it writes Evidence (unlike Phase 6's Scenario engine),
the data model, the API, the UI, and the precision deviation this phase made on the Phase 0
placeholder it replaced.

**Governing principle:** a decision score is a deterministic, weighted RANKING of hypotheticals
the user already built with Phase 6's Scenario engine -- never a new projection, never an LLM
call, and never the AI-narrator-written, human-approved `Recommendation` text that remains a
separate, later-phase placeholder. Every number traces to an existing `ScenarioResult` row; the
only thing this phase adds is a weighted-average formula and the Evidence that frames it as
advisory, per the README's own governing principle: *"The AI recommends; a human approves."*

## 0. Scope decision: Phase 7 is Decision Scoring only

Approved to proceed following Phase 6's completion report ("continue", no new formal spec). The
spec's remaining bundle (decision scoring, the AI narrator, the verifier, chat orchestration) is
still too broad for one disciplined increment, so -- following the same narrow-scoping
discipline Phase 4, 5, and 6 each used on their own slice of the spec -- this phase was scoped to
**Decision Scoring only**. The AI narrator, the recommendation-approval workflow, the verifier,
and chat orchestration remain explicitly deferred. This also follows the pipeline order the
README's own banner states (`DATA -> INSIGHT -> ROOT CAUSE -> FORECAST -> WHAT-IF -> DECISION ->
RECOMMENDATION -> EVIDENCE`): DECISION is the next stage immediately after WHAT-IF.

Verified against the existing codebase, not just inferred: `app/db/models/recommendations.py`
was read in full before any code was written. `Recommendation` (title, narrative text, status,
confidence, `approved_by`/`approved_at` with a CHECK constraint requiring both when
`status='approved'`, `evidence_refs`) and `VerificationReport` (`recommendation_id`, `passed`,
`checks`) are a separate, later phase's placeholders -- the AI-narrator-written, human-approved
recommendation and its verifier -- and remain completely untouched by this phase.

## 1. Method: a weighted average of a scenario's own ScenarioResult deltas

`app/decisions/engine.py::score_decision()`:

1. Resolve every `scenario_id` the caller named (at least two -- comparing one option against
   itself isn't a decision); `400` if any id is unknown, duplicated, or fewer than two are given.
2. For each scenario, compute up to three criteria, all oriented so "higher is always better":
   - **profitability** = average `gross_profit` `delta_percentage` across the scenario's periods.
   - **growth** = average `revenue` `delta_percentage` across the scenario's periods.
   - **cost_efficiency** = average of the *negated* `cogs` `delta_percentage` -- a cost
     *reduction* (a negative COGS delta) scores positively, a cost increase scores negatively.
3. **Weighting**: the default is an equal split across all three criteria
   (`criteria_weights=None`). A caller may instead supply weights for any non-empty subset of
   the three; the supplied weights must sum to ~1.0 (tolerance 0.01) and are **rejected outright
   with `400`, never silently renormalized**, if they don't -- the comparison stays exactly what
   was asked for, the same "never fabricate" discipline every prior phase in this project uses.
4. **`score` is `None`, not fabricated via partial reweighting, when a scenario lacks
   `ScenarioResult` data for *any one* of the criteria actually being weighted.** A revenue-only
   scenario has no `gross_profit`/`cogs` rows at all (Phase 6 only derives `gross_profit` where
   both drivers had a baseline), so weighting in `profitability` or `cost_efficiency` against it
   correctly comes back unscored rather than quietly scoring on just `growth`.
5. Options are ranked by composite score, highest first, ties broken by scenario title for a
   deterministic order; an unscored option's `rank` is `None` too -- there is nothing to rank an
   unscored option against the others on.
6. **`status="insufficient_data"`** (every option unscored) only when *none* of the compared
   scenarios had data for *any* weighted criterion -- the API surfaces this as a `200` with the
   status and a `status_reason`, the same "this is itself a valid, informative answer" pattern
   every prior phase established for its own sufficiency gate.

This is a deliberately simple method: a decision score is "how did each scenario's own numbers
compare, on the criteria you said matter," not a new model, a Monte Carlo simulation, or an
LLM-generated judgment. A more elaborate approach (learned weights, non-linear scoring, risk-
adjusted criteria) would need its own validation story -- explicitly out of scope here.

## 2. Why this phase writes Evidence (unlike Phase 6's Scenario engine)

Phase 6 deliberately wrote **no** Evidence: a scenario is an explicit hypothetical the user is
constructing, not a claim this system is making. A decision score is different -- it **is** a
claim this system is making: an opinion about which of the user's own hypotheticals looks better
by the criteria they weighted. That is exactly what Evidence's `claim_type="recommendation"`
value was reserved for back in Phase 4 and never produced until now.

`app/decisions/evidence.py` writes:

- **One FACT row per `DecisionRun`**, regardless of outcome -- what was compared, with what
  weights (`record_comparison_summary`). This documents the comparison itself as a fact: these
  scenarios were compared, with these weights, deterministically.
- **One RECOMMENDATION row per *scored* `DecisionOption`** (`record_recommendation`) -- an
  unscored option gets no recommendation row, since there is nothing to recommend without a
  score. The claim text explicitly frames the ranking as advisory: *"This is an advisory ranking
  produced by a deterministic formula, not a decision -- a human approves before any action is
  taken."* Never a certainty claim, never a command.

## 3. Data model

Phase 0 reserved a `DecisionOption` placeholder table (`scenario_id`, `title`, `score`,
`rationale` -- no run grouping at all). Phase 7 replaces it with a real, normalized pair in its
own new file (`app/db/models/decision.py`), the same way Phase 5 replaced the Phase 0 `Forecast`
placeholder and Phase 6 replaced the Phase 0 `Scenario` placeholder:

- **`DecisionRun`**: `name`, `description`, `criteria_weights` (JSON -- the weights actually
  used, either supplied or the default equal split, so a run is self-describing without
  recomputing anything), `status` (`completed` | `insufficient_data`), `status_reason`.
- **`DecisionOption`**: `decision_run_id` (FK, `NOT NULL`/`CASCADE` -- true ownership, an option
  has no meaning outside the run that produced it, mirroring `ScenarioResult.scenario_id`),
  `scenario_id` (FK, nullable, `SET NULL` -- mirroring `Scenario.revenue_forecast_run_id`'s own
  pattern: a scored option's score/breakdown/rationale is itself a historical record with
  independent value, so deleting the `Scenario` it was computed from must not silently destroy
  that record, only lose its traceability link), `title`, `score`, `rank` (both nullable --
  `None` together for an unscored option), `criteria_breakdown` (JSON -- one entry per weighted
  criterion, `{weight, value, weighted?}`, so a user can see exactly how `score` was built rather
  than trusting an opaque number), `rationale` (a short, deterministically generated sentence,
  never LLM-written).
- **`Evidence`** gains two more nullable FKs (`decision_run_id`, `decision_option_id`),
  independent of the Phase 5/6 pairs already there -- one Evidence row never belongs to more
  than one of Issue, Forecast, or DecisionOption.

**Deviation from the Phase 0 placeholder's own column precision**: `DecisionOption.score` was
originally `Numeric(6, 3)` (max magnitude 999.999). Since `score` is a weighted average of
`ScenarioResult.delta_percentage` values -- which can themselves reach the same +/-1000% range a
`Scenario`'s own `adjustment_pct` is allowed to -- a legitimate extreme scenario could overflow
that precision. Widened to `Numeric(12, 4)`, matching `ScenarioResult.delta_percentage`'s own
precision, before any code was written against the column.

As with every prior phase's migration, Alembic's autogenerate caught the CheckConstraint on the
brand-new `decision_runs.status` column automatically; this phase's migration needed no
hand-added CheckConstraint beyond that, since no *existing* table's enum-like column was altered
this time (the recurring gap every prior phase's migration hit).

## 4. API

All endpoints are under `/api/v1`, take a validated Pydantic model or a plain path parameter:

| Method | Path | Purpose |
|---|---|---|
| POST | `/decisions` | `{name, description?, scenario_ids, criteria_weights?}` -> score and persist a comparison |
| GET | `/decisions` | List decision runs, most recent first |
| GET | `/decisions/{id}` | One decision run with all its ranked `DecisionOption` rows |

Fewer than two `scenario_ids` is rejected by Pydantic (`422`, `min_length=2`) before the engine
is ever called. An unknown `scenario_id`, a duplicate, or `criteria_weights` that don't sum to
~1.0 or name an unknown criterion all return `400` from the engine's own validation. Every
`DecisionOptionOut` carries an `evidence_id` (the option's RECOMMENDATION row, `null` if
unscored) and every `DecisionRunOut` carries a `fact_evidence_id` (the run's FACT row, always
present) -- both reachable via the existing shared `GET /evidence/{id}` endpoint, the same
pattern Phase 5 established for `Forecast.evidence_id`/`ForecastRun.fit_evidence_id`. This also
meant proactively adding `decision_run_id`/`decision_option_id` to the shared `EvidenceOut`
schema and router up front, rather than discovering the gap retroactively the way Phase 5 had to
for `forecast_run_id`/`forecast_id`.

## 5. UI

`frontend/src/pages/DecisionPage.tsx` ("Decisions" tab): a name field, a checklist of existing
Scenarios to compare (at least two), three optional per-criterion weight inputs (blank means
"use the default equal split"; filling in any of them requires them to sum to ~1.0, exactly as
the API enforces), and a "Compare" action. Results show:

- **`DecisionChart`** (Recharts, horizontal bar) -- composite score per *scored* option, bars
  colored by rank. Unlike `ForecastChart`/`ScenarioChart`, there is no time axis here: a decision
  score is a single ranking number per option, not a series. Unscored options are never plotted
  -- there is nothing to bar-chart about a number that was never fabricated -- and are listed in
  the table below instead, with their rationale explaining what data was missing.
- A ranked options table (rank, scenario, score, rationale, an Evidence drawer link per scored
  option) and a link to the run's own comparison-summary Evidence, reusing the shared
  `components/evidence/` drawer and claim-type badge introduced in Phase 5 -- "recommendation"
  was already styled there (reserved since Phase 4), so no UI changes were needed to display it.

## 6. Testing and verification

17 new backend tests (`tests/decisions/`): engine math, weighting validation, sufficiency-gating,
and Evidence-writing against directly-constructed `Scenario`/`ScenarioResult` rows with the same
explicit, self-contained delete-then-rollback control over table state `tests/scenarios/
test_engine.py` established (`test_engine.py`), and the HTTP layer including both Evidence
endpoints (`test_api.py`). Full backend regression: **330/330 passing**, ruff + mypy `--strict`
clean. 2 new frontend tests (`DecisionChart.test.tsx`, asserting only on the static heading
since Recharts' `ResponsiveContainer` never gets real dimensions under jsdom -- the same
constraint `ForecastChart.test.tsx`/`ScenarioChart.test.tsx` already work around); full frontend
suite **22/22 passing**, ESLint + `tsc` clean, production build succeeds.

Live smoke-tested against the real dev database: generated revenue/COGS baseline forecasts, ran
a "Growth push" (+12% revenue) and a "Cost discipline" (-8% COGS) scenario against them, then
compared the two with the default equal weights. Confirmed the composite scores, per-criterion
breakdown, and rank came back as expected ("Growth push" ranked first on this data), and that
both the run's FACT evidence and the winning option's RECOMMENDATION evidence are reachable
through the existing `GET /evidence/{id}` endpoint with the correct `decision_run_id`/
`decision_option_id` back-references.
