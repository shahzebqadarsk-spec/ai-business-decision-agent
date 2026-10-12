import { lazy, Suspense } from "react";
import type { PlotlyChartProps } from "./PlotlyChart";

const PlotlyChart = lazy(() => import("./PlotlyChart").then((m) => ({ default: m.PlotlyChart })));

export function LazyPlotlyChart(props: PlotlyChartProps) {
  return (
    <Suspense fallback={<div className="h-64 animate-pulse rounded bg-slate-100" />}>
      <PlotlyChart {...props} />
    </Suspense>
  );
}
