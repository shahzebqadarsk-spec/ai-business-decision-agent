# AI Business Decision Agent

Advanced prototype of an AI decision-support system for management, demonstrated on a
**synthetic** textile manufacturer, *PakManufacture Pvt Ltd*.

```
DATA -> INSIGHT -> ROOT CAUSE -> FORECAST -> WHAT-IF -> DECISION -> RECOMMENDATION -> EVIDENCE
```

The AI recommends; a human approves. Every number comes from deterministic analytics, never
from the language model.

> **Status: Phase 0 (foundation), Phase 1 (synthetic data), Phase 2 (ingestion), Phase 3
> (KPI engine + dashboard), Phase 4 (problem detection + root-cause/driver analysis +
> evidence), Phase 5 (forecasting engine, self-scoped), Phase 6 (scenario/what-if analysis,
> self-scoped), and Phase 7 (decision scoring, self-scoped) complete. The AI narrator, the
> recommendation-approval workflow, the verifier, and chat orchestration remain explicitly
> deferred and have not started - awaiting approval.**
> See [docs/DECISIONS.md](docs/DECISIONS.md) for locked decisions and deviations,
> [docs/VERSIONS.md](docs/VERSIONS.md) for verified dependency versions,
> [docs/SYNTHETIC_DATA.md](docs/SYNTHETIC_DATA.md) for the Phase 1 dataset design,
> [docs/PHASE_3_KPI_ENGINE.md](docs/PHASE_3_KPI_ENGINE.md) for the KPI catalog, formulas,
> and dashboard behavior,
> [docs/PHASE_4_RCA_ENGINE.md](docs/PHASE_4_RCA_ENGINE.md) for issue detection, materiality,
> RCA formulas, the Evidence model, and the Driver Analysis UI,
> [docs/PHASE_5_FORECASTING_ENGINE.md](docs/PHASE_5_FORECASTING_ENGINE.md) for the forecasting
> methodology, sufficiency gating, backtest diagnostic, and the Forecasting UI,
> [docs/PHASE_6_SCENARIO_ENGINE.md](docs/PHASE_6_SCENARIO_ENGINE.md) for the scenario
> methodology, why it writes no Evidence, and the Scenario / What-If UI, and
> [docs/PHASE_7_DECISION_SCORING.md](docs/PHASE_7_DECISION_SCORING.md) for the decision-scoring
> methodology, why it does write Evidence, and the Decisions UI.

## What exists so far

| Area | Where | State |
|---|---|---|
| FastAPI backend, settings, structured logging, request IDs | `backend/app/` | working |
| PostgreSQL schema (18 platform tables) + Alembic migration | `backend/app/db/` | working, drift-checked |
| Provider-independent LLM layer (DeepSeek, offline mock, router, structured-output repair, call recording) | `backend/app/llm/`, `backend/config/llm_routing.yaml` | working |
| Auth stub (bearer token) and audit-log helper | `backend/app/api/deps.py`, `backend/app/audit.py` | working |
| React + TypeScript + Tailwind shell, status page, Plotly/Recharts check page | `frontend/` | working |
| Docker Compose (db, backend, frontend), read-only analytics DB role | `docker-compose.yml`, `docker/` | config validated; see caveats |
| Deterministic synthetic data generator (36 months, 5 planted problems, clean + messy variants) | `synthetic_data/generator/` | working, seed-robustness tested |
| Ingestion: upload, profiling, data-quality checks, semantic mapping, canonical materialization | `backend/app/ingestion/`, `frontend/src/pages/IngestionPage.tsx` | working |
| Deterministic KPI engine (21 KPIs, 8 computable), time-period/comparison engine, dimensional breakdowns, append-only provenance | `backend/app/kpi/` | working - see [docs/PHASE_3_KPI_ENGINE.md](docs/PHASE_3_KPI_ENGINE.md) |
| Executive Dashboard (KPI cards, Plotly YoY trend, Recharts breakdowns, customer tables) | `frontend/src/pages/DashboardPage.tsx` | working |
| Deterministic issue detection (8 detectors), configuration-driven materiality, RCA/driver-analysis decomposition, Evidence model with full lineage | `backend/app/rca/` | working - see [docs/PHASE_4_RCA_ENGINE.md](docs/PHASE_4_RCA_ENGINE.md) |
| Issues & Driver Analysis UI (issue list, contribution bar charts, waterfall charts, Evidence drawer) | `frontend/src/pages/DriverAnalysisPage.tsx` | working |
| Deterministic forecasting engine (trend+seasonal decomposition, prediction intervals, backtest diagnostic, sufficiency gating) | `backend/app/forecasting/` | working - see [docs/PHASE_5_FORECASTING_ENGINE.md](docs/PHASE_5_FORECASTING_ENGINE.md) |
| Forecasting UI (metric/horizon/confidence controls, history+forecast chart with confidence band, Evidence drawer) | `frontend/src/pages/ForecastPage.tsx` | working |
| Deterministic Scenario/What-If engine (percentage shocks on baseline forecasts, derived gross-profit/margin, no Evidence by design) | `backend/app/scenarios/` | working - see [docs/PHASE_6_SCENARIO_ENGINE.md](docs/PHASE_6_SCENARIO_ENGINE.md) |
| Scenario/What-If UI (driver-adjustment controls, baseline-vs-scenario chart, results table) | `frontend/src/pages/ScenarioPage.tsx` | working |
| Deterministic Decision Scoring engine (weighted profitability/growth/cost_efficiency ranking of Scenarios, FACT+RECOMMENDATION Evidence) | `backend/app/decisions/` | working - see [docs/PHASE_7_DECISION_SCORING.md](docs/PHASE_7_DECISION_SCORING.md) |
| Decisions UI (scenario multi-select, optional criteria weights, ranked-options table, composite-score chart, Evidence drawer) | `frontend/src/pages/DecisionPage.tsx` | working |
| Tests, ruff, mypy `--strict`, ESLint, Vitest | everywhere | passing (330 backend + 22 frontend) |

The `Recommendation`/`VerificationReport` DB models (`backend/app/db/models/recommendations.py`)
remain untouched Phase 0 placeholders - the AI narrator, the recommendation-approval workflow,
the verifier, and chat orchestration were explicitly deferred and have not started, no backend
package exists for them yet, and work awaits explicit approval.

## Quick start

### Option A - Docker Compose

```bash
cp .env.example .env          # then set POSTGRES_PASSWORD and ANALYTICS_DB_PASSWORD
docker compose up --build
```

- App: http://localhost:5173  - API docs: http://localhost:8000/api/docs
- The backend container applies migrations on start.
- `.env.example` defaults to `LLM_USE_MOCK=true`, so no API key is needed.

### Option B - run locally (PostgreSQL 16 required)

```bash
make setup                    # creates .env, backend/.venv, installs backend + frontend deps
# create the database and role named in .env (defaults: abda / abda), then:
make migrate
make backend-dev              # terminal 1 -> http://localhost:8000
make frontend-dev             # terminal 2 -> http://localhost:5173
```

### Checks

```bash
make test        # backend (pytest) + frontend (vitest)
make lint        # ruff + eslint
make typecheck   # mypy --strict + tsc
make check       # all of the above
```

DB tests create and drop a throwaway `<db>_test` database on the server in `DATABASE_URL`
(override with `TEST_DATABASE_URL`). If PostgreSQL is unreachable they are **skipped** with a
reason; set `REQUIRE_DB_TESTS=1` (as CI should) to make that a failure instead.

## Configuration

Everything is an environment variable; see [.env.example](.env.example), which documents each one.
Keep comments on their own lines in `.env` (Docker Compose reads text after an empty `KEY=` as the
value). Secrets are `SecretStr` and never logged or returned by the API.

**Using DeepSeek for real:** set `LLM_USE_MOCK=false` and `DEEPSEEK_API_KEY=...`. The key is read
server-side only. Model names and prices are in `backend/config/llm_routing.yaml` and were taken
from DeepSeek's docs on 2026-10-07 - verify them, and make one live smoke call, before relying on
them (Phase 0 made none).

## Layout

```
backend/    FastAPI app, analytics modules (placeholders), LLM layer, Alembic, tests
frontend/   React + Vite + TypeScript + Tailwind v4 (Plotly lazy-loaded, Recharts for sparklines)
docker/     PostgreSQL init scripts (read-only analytics role)
docs/       DECISIONS.md, VERSIONS.md, SYNTHETIC_DATA.md, PHASE_3_KPI_ENGINE.md,
            PHASE_4_RCA_ENGINE.md, PHASE_5_FORECASTING_ENGINE.md, PHASE_6_SCENARIO_ENGINE.md,
            PHASE_7_DECISION_SCORING.md
synthetic_data/   (Phase 1) seeded generator for PakManufacture Pvt Ltd
```

## Design rules that are already enforced

- Synthetic data only: `SYNTHETIC_DATA_ONLY=false` is rejected at startup.
- API keys live in environment variables, server-side; `GET /llm/status` reports only whether a
  key exists.
- `llm_calls` records provider, model, purpose, tokens, cost and latency - never prompts.
- A recommendation cannot be stored as `approved` without an approver and timestamp (DB CHECK).
- Fiscal-year start is configurable (1 = calendar year for the demo; 7 = Pakistan's statutory year).
- Default comparison is YoY; QoQ is a setting.
