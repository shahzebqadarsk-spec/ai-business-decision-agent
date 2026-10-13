import { useMemo } from "react";
import { Card } from "../ui/card";
import { LazyPlotlyChart } from "../../charts/LazyPlotlyChart";
import { useDisplayCurrency } from "../../hooks/useCurrency";
import type { DimensionBreakdownRow } from "../../types/kpi";

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const LINE_COLORS = ["#94a3b8", "#1d4ed8", "#059669", "#d97706", "#dc2626"];

/** Overlays one line per year (Jan-Dec on the x-axis) so the person can compare years
 * directly, rather than one long run of months -- the kind of comparison Plotly is used
 * for here, versus the simple single-series sparklines Recharts handles elsewhere. */
export function RevenueTrendChart({ rows }: { rows: DimensionBreakdownRow[] }) {
  const currency = useDisplayCurrency() ?? "PKR";
  const { years, series } = useMemo(() => {
    const byYear = new Map<string, (number | null)[]>();
    for (const row of rows) {
      if (!row.dimension_value) continue;
      const [year, month] = row.dimension_value.split("-");
      if (!byYear.has(year)) byYear.set(year, new Array(12).fill(null));
      const monthIndex = Number(month) - 1;
      byYear.get(year)![monthIndex] = row.value;
    }
    const years = Array.from(byYear.keys()).sort();
    return { years, series: byYear };
  }, [rows]);

  if (years.length === 0) {
    return (
      <Card>
        <h3 className="mb-2 text-sm font-semibold text-slate-500">Revenue trend</h3>
        <p className="text-sm text-slate-400">No data available.</p>
      </Card>
    );
  }

  return (
    <Card>
      <h3 className="mb-2 text-sm font-semibold text-slate-500">Monthly revenue by year</h3>
      <LazyPlotlyChart
        data={years.map((year, i) => ({
          x: MONTH_LABELS,
          y: series.get(year),
          type: "scatter",
          mode: "lines+markers",
          name: year,
          line: { color: LINE_COLORS[i % LINE_COLORS.length] },
          connectgaps: false,
        }))}
        layout={{
          autosize: true,
          height: 320,
          margin: { t: 10, r: 10, l: 50, b: 30 },
          yaxis: { title: { text: currency }, tickformat: ",.0s" },
          legend: { orientation: "h", y: -0.2 },
        }}
        useResizeHandler
        style={{ width: "100%" }}
        config={{ displayModeBar: false }}
      />
    </Card>
  );
}
