import { Card } from "../components/ui/card";
import { KpiSparkline } from "../charts/KpiSparkline";
import { LazyPlotlyChart } from "../charts/LazyPlotlyChart";

const SPARKLINE_DATA = [
  { month: "Jan", value: 10 },
  { month: "Feb", value: 14 },
  { month: "Mar", value: 12 },
  { month: "Apr", value: 18 },
];

export function ChartCheckPage() {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Card>
        <h2 className="mb-2 text-sm font-semibold text-slate-500">Recharts sparkline</h2>
        <KpiSparkline data={SPARKLINE_DATA} />
      </Card>
      <Card>
        <h2 className="mb-2 text-sm font-semibold text-slate-500">Plotly chart (lazy-loaded)</h2>
        <LazyPlotlyChart
          data={[{ x: [1, 2, 3], y: [2, 6, 3], type: "scatter", mode: "lines+markers" }]}
          layout={{ width: 320, height: 240, margin: { t: 10 } }}
        />
      </Card>
    </div>
  );
}
