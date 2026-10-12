import { useState } from "react";
import { Card } from "../components/ui/card";
import { ForecastChart } from "../components/forecast/ForecastChart";
import { EvidenceDrawer } from "../components/evidence/EvidenceDrawer";
import { useForecastRuns, useGenerateForecast, useHistoricalSeries } from "../hooks/useForecast";
import { formatCount, formatPkr } from "../lib/format";
import { CONFIDENCE_LEVELS, FORECAST_METRICS } from "../types/forecast";
import type { ConfidenceLevel, ForecastMetric, ForecastRun } from "../types/forecast";

const CURRENCY_METRICS: ForecastMetric[] = ["revenue", "cogs"];

function formatMetricValue(metric: string, value: number): string {
  return CURRENCY_METRICS.includes(metric as ForecastMetric) ? formatPkr(value) : formatCount(value);
}

function parsePeriodYear(periodKey: string): number {
  return Number(periodKey.slice(0, 4));
}

function RunDiagnostics({ run }: { run: ForecastRun }) {
  return (
    <Card className="space-y-1 text-xs">
      <p className="mb-1 font-semibold text-slate-500">Fit diagnostics</p>
      <p className="flex justify-between gap-3">
        <span className="text-slate-400">History used</span>
        <span className="text-slate-700">
          {run.history_start_period} to {run.history_end_period} ({run.history_periods} months)
        </span>
      </p>
      <p className="flex justify-between gap-3">
        <span className="text-slate-400">Method</span>
        <span className="text-slate-700">
          {run.method_name} v{run.method_version}
        </span>
      </p>
      {run.holdout_periods !== null && (
        <p className="flex justify-between gap-3">
          <span className="text-slate-400">
            Holdout backtest ({run.holdout_periods} months withheld)
          </span>
          <span className="text-slate-700">
            MAE {formatMetricValue(run.metric, run.holdout_mae ?? 0)}
            {run.holdout_mape_pct !== null ? `, MAPE ${run.holdout_mape_pct.toFixed(1)}%` : ""}
          </span>
        </p>
      )}
      <p className="pt-1 text-slate-400">
        The backtest refits on history minus the holdout purely as a transparency diagnostic --
        the delivered forecast is always refit on the complete history.
      </p>
    </Card>
  );
}

export function ForecastPage() {
  const [metric, setMetric] = useState<ForecastMetric>("revenue");
  const [horizonPeriods, setHorizonPeriods] = useState(6);
  const [confidenceLevel, setConfidenceLevel] = useState<ConfidenceLevel>(0.8);
  const [activeRun, setActiveRun] = useState<ForecastRun | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);

  const runsQuery = useForecastRuns(metric);
  const generateMutation = useGenerateForecast();

  const run = activeRun ?? runsQuery.data?.[0] ?? null;
  const historicalQuery = useHistoricalSeries(
    run?.metric,
    run ? parsePeriodYear(run.history_start_period) : undefined,
    run ? parsePeriodYear(run.history_end_period) : undefined,
  );

  function handleGenerate() {
    generateMutation.mutate(
      { metric, horizonPeriods, confidenceLevel },
      { onSuccess: (newRun) => setActiveRun(newRun) },
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Forecasting</h2>
      </div>
      <p className="text-xs text-slate-400">
        A deterministic trend + seasonal projection (no ARIMA/ML library), always fit on the
        complete available history for the chosen metric. Every forecasted point is Evidence of
        type "inference" -- a projection, never a fact or a guaranteed outcome.
      </p>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col text-xs text-slate-500">
            Metric
            <select
              value={metric}
              onChange={(e) => {
                setMetric(e.target.value as ForecastMetric);
                setActiveRun(null);
              }}
              className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
            >
              {FORECAST_METRICS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-xs text-slate-500">
            Horizon (months, 1-24)
            <input
              type="number"
              min={1}
              max={24}
              value={horizonPeriods}
              onChange={(e) => setHorizonPeriods(Number(e.target.value))}
              className="mt-1 w-24 rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </label>
          <label className="flex flex-col text-xs text-slate-500">
            Confidence level
            <select
              value={confidenceLevel}
              onChange={(e) => setConfidenceLevel(Number(e.target.value) as ConfidenceLevel)}
              className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
            >
              {CONFIDENCE_LEVELS.map((c) => (
                <option key={c} value={c}>
                  {(c * 100).toFixed(0)}%
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generateMutation.isPending}
            className="rounded bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
          >
            {generateMutation.isPending ? "Generating..." : "Generate forecast"}
          </button>
        </div>
        {generateMutation.isError && (
          <p className="mt-2 text-xs text-red-600">
            {generateMutation.error instanceof Error
              ? generateMutation.error.message
              : "Could not generate a forecast for this metric/horizon."}
          </p>
        )}
      </Card>

      {runsQuery.isLoading && (
        <Card>
          <p className="text-sm text-slate-500">Loading forecast runs...</p>
        </Card>
      )}
      {runsQuery.isError && (
        <Card>
          <p className="text-sm text-red-600">Could not reach the backend.</p>
        </Card>
      )}

      {!run && runsQuery.data && runsQuery.data.length === 0 && (
        <Card>
          <p className="text-sm text-slate-400">
            No forecast runs yet for {metric}. Generate one above.
          </p>
        </Card>
      )}

      {run && run.status === "insufficient_data" && (
        <Card>
          <p className="text-sm text-amber-700">
            Not enough history to forecast {run.metric}: {run.status_reason}
          </p>
        </Card>
      )}

      {run && run.status === "completed" && (
        <>
          <ForecastChart
            metric={run.metric}
            confidenceLevel={run.confidence_level}
            historical={historicalQuery.data ?? []}
            forecasts={run.forecasts}
            onSelectEvidence={setSelectedEvidenceId}
          />

          <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
            <Card className="overflow-x-auto">
              <p className="mb-2 text-sm font-semibold text-slate-600">Forecasted periods</p>
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-400">
                    <th className="pb-1 pr-3">Period</th>
                    <th className="pb-1 pr-3">Point estimate</th>
                    <th className="pb-1 pr-3">
                      {(run.confidence_level * 100).toFixed(0)}% interval
                    </th>
                    <th className="pb-1">Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {run.forecasts.map((f) => (
                    <tr key={f.id} className="border-t border-slate-100">
                      <td className="py-1 pr-3 text-slate-700">{f.period_key}</td>
                      <td className="py-1 pr-3 text-slate-700">
                        {formatMetricValue(run.metric, f.point_estimate)}
                      </td>
                      <td className="py-1 pr-3 text-slate-500">
                        {f.lower_bound !== null && f.upper_bound !== null
                          ? `${formatMetricValue(run.metric, f.lower_bound)} - ${formatMetricValue(run.metric, f.upper_bound)}`
                          : "—"}
                      </td>
                      <td className="py-1">
                        {f.evidence_id && (
                          <button
                            type="button"
                            onClick={() => setSelectedEvidenceId(f.evidence_id)}
                            className="text-blue-700 underline"
                          >
                            View
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            <div className="space-y-3">
              <RunDiagnostics run={run} />
              {run.fit_evidence_id && (
                <button
                  type="button"
                  onClick={() => setSelectedEvidenceId(run.fit_evidence_id)}
                  className="text-xs text-blue-700 underline"
                >
                  View fit evidence
                </button>
              )}
            </div>
          </div>
        </>
      )}

      <EvidenceDrawer evidenceId={selectedEvidenceId} onClose={() => setSelectedEvidenceId(null)} />
    </div>
  );
}
