# Verified dependency versions

Captured from the actual rebuild environment on 2026-10-07. Pin these (or close patch
versions) if you set up a new environment; "Requested" shows what the manifest asks for,
"Resolved" shows what was actually installed and verified.

## Runtime

| Tool | Version |
|---|---|
| Python | 3.12.3 |
| Node.js | 22.22.0 |
| npm | 10.9.4 |
| PostgreSQL | 16.15 |

## Backend (`backend/pyproject.toml`)

| Package | Resolved |
|---|---|
| fastapi | 0.142.2 |
| uvicorn | 0.54.0 |
| sqlalchemy | 2.1.3 |
| alembic | 1.20.0 |
| psycopg[binary] | 3.3.6 |
| pydantic | 2.13.5 |
| pydantic-settings | 2.15.0 |
| openai | 3.26.0 |
| pandas | 3.0.6 |
| numpy | 2.5.3 |
| openpyxl | 3.1.5 |
| python-magic | 0.4.27 |
| PyYAML | 6.0.3 |
| python-multipart | 0.0.32 |
| pytest | 9.1.1 |
| ruff | 0.16.10 |
| mypy | 2.4.0 |
| pandas-stubs | 3.0.5.260914 |
| types-PyYAML | 6.0.12.20260906 |

## Frontend (`frontend/package.json`)

| Package | Resolved |
|---|---|
| react / react-dom | 18.3.1 |
| @tanstack/react-query | 5.104.1 |
| react-plotly.js | 2.6.0 (its `plotly.js` peer overridden to `plotly.js-dist-min@2.35.3`) |
| recharts | 2.15.4 |
| vite | 5.4.21 |
| vitest | 2.1.9 |
| typescript | 5.9.3 |
| typescript-eslint | 8.71.1 |
| eslint | 9.39.5 |
| tailwindcss / @tailwindcss/postcss | 4.3.3 |

**Plotly aliasing note:** `react-plotly.js` pulls in the full `plotly.js` (several MB) by
default. The `overrides` block in `package.json` redirects that peer dependency to
`plotly.js-dist-min` (the pre-built, smaller distribution), and `src/charts/PlotlyChart.tsx`
imports it explicitly via `react-plotly.js/factory` + `import Plotly from "plotly.js-dist-min"`
rather than the package's default entry point, which does not resolve correctly against the
lighter bundle. A local type declaration (`src/types/plotly-js-dist-min.d.ts`) re-exports the
`@types/plotly.js` types for the aliased module since no first-party types ship for
`plotly.js-dist-min` itself. The production build confirms this chunk is code-split into its
own `PlotlyChart-*.js` file, lazy-loaded via `LazyPlotlyChart`, and not bundled into the main
entry chunk.

**DeepSeek pricing/model names** in `backend/config/llm_routing.yaml` were taken from
DeepSeek's public pricing page on 2026-10-07 and are for cost-estimation purposes only; they
are not verified against a live API call (Phase 0/1/2 run entirely against the mock
provider). Re-verify both the model identifiers and the per-1k-token prices before relying on
real-money cost figures.
