import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "../ui/card";
import { formatCount, formatPkr } from "../../lib/format";
import type { ForecastMetric, ForecastPoint } from "../../types/forecast";

interface HistoricalRow {
  dimension_value: string | null;
  value: number | null;
}

interface ChartRow {
  period: string;
  actual: number | null;
  pointEstimate: number | null;
  band: [number, number] | null;
  evidenceId: string | null;
}

const CURRENCY_METRICS: ForecastMetric[] = ["revenue", "cogs"];

function valueFormatter(metric: string): (v: number) => string {
  return CURRENCY_METRICS.includes(metric as ForecastMetric) ? formatPkr : formatCount;
}

function buildRows(historical: HistoricalRow[], forecasts: ForecastPoint[]): ChartRow[] {
  const rows: ChartRow[] = historical
    .filter((r) => r.dimension_value !== null)
    .map((r) => ({
      period: r.dimension_value as string,
      actual: r.value,
      pointEstimate: null,
      band: null,
      evidenceId: null,
    }));

  // The first forecasted point continues the actual line visually (so the chart reads as one
  // continuous series rather than a gap followed by a disconnected forecast segment).
  const lastActual = rows.length > 0 ? rows[rows.length - 1] : undefined;
  const bridge: ChartRow[] = lastActual
    ? [{ ...lastActual, pointEstimate: lastActual.actual, band: null }]
    : [];

  const forecastRows: ChartRow[] = [...forecasts]
    .sort((a, b) => a.horizon_index - b.horizon_index)
    .map((f) => ({
      period: f.period_key,
      actual: null,
      pointEstimate: f.point_estimate,
      band: f.lower_bound !== null && f.upper_bound !== null ? [f.lower_bound, f.upper_bound] : null,
      evidenceId: f.evidence_id,
    }));

  return [...rows.slice(0, -1), ...bridge, ...forecastRows];
}

/** Historical actuals (solid line) feeding into the forecasted horizon (dashed-feel via a
 * separate series) with a shaded prediction-interval band -- the band visibly widens further
 * into the future because `predict_interval`'s leverage term grows with distance from the
 * historical window (see app/forecasting/model.py), never a fixed +/-X% band. */
export function ForecastChart({
  metric,
  confidenceLevel,
  historical,
  forecasts,
  onSelectEvidence,
}: {
  metric: string;
  confidenceLevel: number;
  historical: HistoricalRow[];
  forecasts: ForecastPoint[];
  onSelectEvidence?: (evidenceId: string) => void;
}) {
  const rows = buildRows(historical, forecasts);
  const fmt = valueFormatter(metric);

  if (rows.length === 0) {
    return (
      <Card>
        <p className="text-sm text-slate-400">No data available to chart.</p>
      </Card>
    );
  }

  return (
    <Card>
      <h4 className="mb-1 text-sm font-semibold text-slate-600">
        {metric} -- history and {forecasts.length}-period forecast
      </h4>
      <p className="mb-2 text-xs text-slate-400">
        Shaded band is the {(confidenceLevel * 100).toFixed(0)}% prediction interval; it is an
        inference about the future, not a fact and not a guaranteed outcome.
      </p>
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={rows} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="period" fontSize={11} />
          <YAxis tickFormatter={(v: number) => fmt(v)} fontSize={11} width={70} />
          <Tooltip
            formatter={(value: unknown, name: string) => {
              if (Array.isArray(value)) return [`${fmt(value[0])} - ${fmt(value[1])}`, "Interval"];
              return [typeof value === "number" ? fmt(value) : "—", name];
            }}
          />
          <Legend />
          <Area
            type="monotone"
            dataKey="band"
            name="Prediction interval"
            stroke="none"
            fill="#a855f7"
            fillOpacity={0.15}
            isAnimationActive={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="actual"
            name="Actual"
            stroke="#1d4ed8"
            dot={false}
            strokeWidth={2}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="pointEstimate"
            name="Forecast"
            stroke="#a855f7"
            strokeDasharray="5 3"
            dot={{
              r: 3,
              onClick: (point: unknown) => {
                const p = point as { payload?: ChartRow };
                if (p.payload?.evidenceId && onSelectEvidence) onSelectEvidence(p.payload.evidenceId);
              },
              cursor: onSelectEvidence ? "pointer" : "default",
            }}
            strokeWidth={2}
            isAnimationActive={false}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </Card>
  );
}
