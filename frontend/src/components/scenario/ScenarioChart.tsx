import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card } from "../ui/card";
import { formatCount, formatPkr } from "../../lib/format";
import type { ScenarioMetric, ScenarioResult } from "../../types/scenario";

const CURRENCY_METRICS: ScenarioMetric[] = ["revenue", "cogs", "gross_profit"];

function valueFormatter(metric: string): (v: number) => string {
  if (metric === "gross_margin_pct") return (v) => `${v.toFixed(1)}%`;
  return CURRENCY_METRICS.includes(metric as ScenarioMetric) ? formatPkr : formatCount;
}

/** Baseline (the unadjusted Phase 5 forecast) vs. scenario (the same periods after applying
 * the requested percentage shock) for one metric, period by period -- unlike `ForecastChart`,
 * there is no confidence band here: a scenario is a deliberate, deterministic hypothetical the
 * user constructed, not a statistically fitted estimate, so there is no interval to draw. */
export function ScenarioChart({ metric, results }: { metric: string; results: ScenarioResult[] }) {
  const rows = results
    .filter((r) => r.metric === metric)
    .sort((a, b) => a.horizon_index - b.horizon_index)
    .map((r) => ({
      period: r.period_key,
      baseline: r.baseline_value,
      scenario: r.scenario_value,
    }));
  const fmt = valueFormatter(metric);

  if (rows.length === 0) {
    return (
      <Card>
        <p className="text-sm text-slate-400">No {metric} results in this scenario.</p>
      </Card>
    );
  }

  return (
    <Card>
      <h4 className="mb-2 text-sm font-semibold text-slate-600">{metric}: baseline vs. scenario</h4>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={rows} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="period" fontSize={11} />
          <YAxis tickFormatter={(v: number) => fmt(v)} fontSize={11} width={70} />
          <Tooltip formatter={(value: unknown) => (typeof value === "number" ? fmt(value) : "—")} />
          <Legend />
          <Line type="monotone" dataKey="baseline" name="Baseline forecast" stroke="#1d4ed8" dot={false} strokeWidth={2} isAnimationActive={false} />
          <Line type="monotone" dataKey="scenario" name="Scenario" stroke="#059669" strokeDasharray="5 3" dot={{ r: 3 }} strokeWidth={2} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
