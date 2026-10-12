import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import type { ComponentProps } from "react";

const Plot = createPlotlyComponent(Plotly);

export type PlotlyChartProps = ComponentProps<typeof Plot>;

export function PlotlyChart(props: PlotlyChartProps) {
  return <Plot {...props} />;
}
