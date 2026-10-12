import { useState } from "react";
import { Card } from "../components/ui/card";
import { ScenarioChart } from "../components/scenario/ScenarioChart";
import { useForecastRuns } from "../hooks/useForecast";
import { useGenerateScenario, useScenarios } from "../hooks/useScenario";
import { formatCount, formatPkr } from "../lib/format";
import { SCENARIO_METRICS } from "../types/scenario";
import type { Scenario, ScenarioMetric } from "../types/scenario";

const CURRENCY_METRICS: ScenarioMetric[] = ["revenue", "cogs", "gross_profit"];

function formatMetricValue(metric: string, value: number): string {
  if (metric === "gross_margin_pct") return `${value.toFixed(1)}%`;
  return CURRENCY_METRICS.includes(metric as ScenarioMetric) ? formatPkr(value) : formatCount(value);
}

export function ScenarioPage() {
  const [name, setName] = useState("");
  const [revenueAdjustment, setRevenueAdjustment] = useState(0);
  const [cogsAdjustment, setCogsAdjustment] = useState(0);
  const [revenueRunId, setRevenueRunId] = useState<string>("auto");
  const [cogsRunId, setCogsRunId] = useState<string>("auto");
  const [activeScenario, setActiveScenario] = useState<Scenario | null>(null);
  const [chartMetric, setChartMetric] = useState<string>("revenue");

  const revenueRunsQuery = useForecastRuns("revenue");
  const cogsRunsQuery = useForecastRuns("cogs");
  const scenariosQuery = useScenarios();
  const generateMutation = useGenerateScenario();

  const scenario = activeScenario ?? scenariosQuery.data?.[0] ?? null;

  function handleGenerate() {
    generateMutation.mutate(
      {
        name: name.trim() || "Untitled scenario",
        revenue_growth_adjustment_pct: revenueAdjustment,
        cogs_adjustment_pct: cogsAdjustment,
        revenue_forecast_run_id: revenueRunId === "auto" ? null : revenueRunId,
        cogs_forecast_run_id: cogsRunId === "auto" ? null : cogsRunId,
      },
      { onSuccess: (newScenario) => setActiveScenario(newScenario) },
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Scenario / What-If</h2>
      </div>
      <p className="text-xs text-slate-400">
        A deterministic percentage shock applied to an existing forecast -- never its own
        statistical fit. Gross profit and gross margin % are re-derived from the (possibly
        adjusted) revenue and COGS using the same formulas the Dashboard and Driver Analysis
        already use. Run a forecast for revenue/COGS first (on the Forecasting tab) if no
        baseline is available below.
      </p>

      <Card>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col text-xs text-slate-500">
            Scenario name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Faster revenue growth"
              className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </label>
          <label className="flex flex-col text-xs text-slate-500">
            Revenue growth adjustment (%)
            <input
              type="number"
              step={0.5}
              value={revenueAdjustment}
              onChange={(e) => setRevenueAdjustment(Number(e.target.value))}
              className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </label>
          <label className="flex flex-col text-xs text-slate-500">
            COGS adjustment (%)
            <input
              type="number"
              step={0.5}
              value={cogsAdjustment}
              onChange={(e) => setCogsAdjustment(Number(e.target.value))}
              className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </label>
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generateMutation.isPending}
              className="w-full rounded bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
            >
              {generateMutation.isPending ? "Running..." : "Run scenario"}
            </button>
          </div>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col text-xs text-slate-500">
            Revenue baseline forecast
            <select
              value={revenueRunId}
              onChange={(e) => setRevenueRunId(e.target.value)}
              className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="auto">Latest completed run (auto)</option>
              {(revenueRunsQuery.data ?? [])
                .filter((r) => r.status === "completed")
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.history_end_period} +{r.horizon_periods}mo, generated {r.created_at.slice(0, 10)}
                  </option>
                ))}
            </select>
          </label>
          <label className="flex flex-col text-xs text-slate-500">
            COGS baseline forecast
            <select
              value={cogsRunId}
              onChange={(e) => setCogsRunId(e.target.value)}
              className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="auto">Latest completed run (auto)</option>
              {(cogsRunsQuery.data ?? [])
                .filter((r) => r.status === "completed")
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.history_end_period} +{r.horizon_periods}mo, generated {r.created_at.slice(0, 10)}
                  </option>
                ))}
            </select>
          </label>
        </div>

        {generateMutation.isError && (
          <p className="mt-2 text-xs text-red-600">
            {generateMutation.error instanceof Error
              ? generateMutation.error.message
              : "Could not run this scenario."}
          </p>
        )}
      </Card>

      {scenariosQuery.isLoading && (
        <Card>
          <p className="text-sm text-slate-500">Loading scenarios...</p>
        </Card>
      )}
      {scenariosQuery.isError && (
        <Card>
          <p className="text-sm text-red-600">Could not reach the backend.</p>
        </Card>
      )}
      {!scenario && scenariosQuery.data && scenariosQuery.data.length === 0 && (
        <Card>
          <p className="text-sm text-slate-400">No scenarios yet. Run one above.</p>
        </Card>
      )}

      {scenario && scenario.status === "insufficient_data" && (
        <Card>
          <p className="text-sm text-amber-700">{scenario.status_reason}</p>
        </Card>
      )}

      {scenario && scenario.status === "completed" && (
        <>
          <Card>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-700">{scenario.name}</p>
              <label className="flex items-center gap-2 text-xs text-slate-500">
                Chart metric
                <select
                  value={chartMetric}
                  onChange={(e) => setChartMetric(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-sm"
                >
                  {SCENARIO_METRICS.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="text-xs text-slate-400">
              Revenue adjustment {scenario.revenue_growth_adjustment_pct > 0 ? "+" : ""}
              {scenario.revenue_growth_adjustment_pct}%, COGS adjustment{" "}
              {scenario.cogs_adjustment_pct > 0 ? "+" : ""}
              {scenario.cogs_adjustment_pct}% over {scenario.horizon_periods} period(s).
            </p>
          </Card>

          <ScenarioChart metric={chartMetric} results={scenario.results} />

          <Card className="overflow-x-auto">
            <p className="mb-2 text-sm font-semibold text-slate-600">All results</p>
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-slate-400">
                  <th className="pb-1 pr-3">Metric</th>
                  <th className="pb-1 pr-3">Period</th>
                  <th className="pb-1 pr-3">Baseline</th>
                  <th className="pb-1 pr-3">Scenario</th>
                  <th className="pb-1">Delta</th>
                </tr>
              </thead>
              <tbody>
                {scenario.results.map((r) => (
                  <tr key={r.id} className="border-t border-slate-100">
                    <td className="py-1 pr-3 text-slate-700">{r.metric}</td>
                    <td className="py-1 pr-3 text-slate-700">{r.period_key}</td>
                    <td className="py-1 pr-3 text-slate-500">
                      {r.baseline_value !== null ? formatMetricValue(r.metric, r.baseline_value) : "—"}
                    </td>
                    <td className="py-1 pr-3 text-slate-700">{formatMetricValue(r.metric, r.scenario_value)}</td>
                    <td className="py-1 text-slate-500">
                      {r.delta_percentage !== null ? `${r.delta_percentage > 0 ? "+" : ""}${r.delta_percentage.toFixed(1)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
